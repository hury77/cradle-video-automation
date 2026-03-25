import os
import requests
import logging
from pathlib import Path
import asyncio
import glob
import shutil
import zipfile


class FileHandler:
    def __init__(self, download_base_path=None):
        self.logger = logging.getLogger(__name__)

        # Default Downloads folder
        if download_base_path is None:
            home = Path.home()
            self.download_base_path = home / "Downloads"
        else:
            self.download_base_path = Path(download_base_path)

        self.logger.info(
            f"FileHandler initialized with base path: {self.download_base_path}"
        )

    async def handle_files_detected(self, websocket, data):
        """Handle FILES_DETECTED message from extension"""
        try:
            cradle_id = data.get("cradleId")
            acceptance_file = data.get("acceptanceFile")
            emission_file = data.get("emissionFile")

            # Inject metadata from message into file_info dicts so Lucid/network handlers have it
            job_number = data.get("jobNumber")
            template_id = data.get("templateId")
            lang_code = data.get("langCode")  # e.g. "IT", "FR", "DE"
            if acceptance_file and isinstance(acceptance_file, dict):
                acceptance_file.setdefault("jobNumber", job_number)
                acceptance_file.setdefault("templateId", template_id)
                acceptance_file.setdefault("langCode", lang_code)
            if emission_file and isinstance(emission_file, dict):
                emission_file.setdefault("jobNumber", job_number)
                emission_file.setdefault("templateId", template_id)
                emission_file.setdefault("langCode", lang_code)

            self.logger.info(f"📁 Processing files for CradleID: {cradle_id} | jobNumber: {job_number} | templateId: {template_id} | langCode: {lang_code}")


            if not cradle_id:
                await self.send_error(websocket, "No CradleID provided")
                return

            # Create (or reuse) cradle folder
            cradle_folder = self.download_base_path / cradle_id
            cradle_folder.mkdir(parents=True, exist_ok=True)

            # ✅ Wyczyść tylko pliki _emis gdy pobieramy NOWY plik emisji z sieci/Lucid.
            # NIE kasujemy gdy emisja to attachment (Chrome API już pobrał plik _emis).
            VIDEO_EXTS = {".mp4", ".mov", ".mxf", ".prores", ".avi", ".mkv",
                          ".MP4", ".MOV", ".MXF", ".PRORES", ".AVI", ".MKV"}
            is_network_emission = emission_file and isinstance(emission_file, dict) and emission_file.get("type") == "network_path"
            if is_network_emission:
                removed = []
                for existing in cradle_folder.iterdir():
                    name_lower = existing.name.lower()
                    is_emis = "_emis." in name_lower or name_lower.endswith("_emis")
                    if existing.is_file() and is_emis and existing.suffix in VIDEO_EXTS:
                        existing.unlink()
                        removed.append(existing.name)
                if removed:
                    self.logger.info(f"🧹 Cleared {len(removed)} old _emis file(s) from {cradle_id}/: {removed}")
            else:
                self.logger.info(f"🧹 Skipping _emis cleanup — emission is attachment type (Chrome API)")


            self.logger.info(f"📂 Created/verified folder: {cradle_folder}")



            results = {
                "cradle_id": cradle_id,
                "folder": str(cradle_folder),
                "files_downloaded": [],
                "errors": [],
            }

            # Download acceptance file
            if acceptance_file:
                result = await self.download_file(
                    acceptance_file, cradle_folder, "acceptance"
                )
                if result["success"]:
                    # Post-process: Unzip / Rename
                    processed_result = await self._process_downloaded_file(
                        result, cradle_folder, "acceptance"
                    )
                    results["files_downloaded"].append(processed_result)
                else:
                    results["errors"].append(result)

            # Download emission file
            if emission_file:
                result = await self.download_file(
                    emission_file, cradle_folder, "emission"
                )
                if result["success"]:
                    # Post-process: Unzip / Rename
                    processed_result = await self._process_downloaded_file(
                        result, cradle_folder, "emission"
                    )
                    results["files_downloaded"].append(processed_result)
                else:
                    results["errors"].append(result)

            # Send results back to extension
            await self.send_download_results(websocket, results)

        except Exception as e:
            self.logger.error(f"❌ Error handling files: {str(e)}")
            await self.send_error(websocket, f"File handling error: {str(e)}")

    async def download_file(self, file_info, folder_path, file_type):
        """Download single file - handles both attachments and network paths"""
        try:
            # Check if it's a network path (emission file)
            if file_info.get("type") == "network_path" and file_info.get("path"):
                self.logger.info(f"🌐 Detected network path for {file_type}")
                cradle_id = folder_path.name  # Get CradleID from folder name

                # Route lucid:// links to dedicated Lucid handler
                if file_info.get("path") == "__lucid__" and file_info.get("lucidFilespace"):
                    self.logger.info(f"🔗 Routing to Lucid handler for filespace: {file_info['lucidFilespace']}")
                    return await self.handle_lucid_emission_file(
                        file_info, folder_path, cradle_id
                    )

                return await self.handle_network_emission_file(
                    file_info, folder_path, cradle_id
                )

            # 🔥 NOWE: Handle emission attachments with suffix
            if file_type == "emission" and file_info.get("type") == "attachment":
                return await self.handle_emission_attachment(file_info, folder_path)

            # Regular file download (acceptance attachments)
            url = file_info.get("url")
            original_name = file_info.get(
                "name", f"{file_type}_{file_info.get('row', 'unknown')}.mp4"
            )

            if not url:
                return {"success": False, "type": file_type, "error": "No URL provided"}

            self.logger.info(f"⬇️ Downloading {file_type}: {original_name}")
            self.logger.info(f"   URL: {url}")

            # Download file with headers for better compatibility
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "*/*",
                "Referer": "https://cradle.egplusww.pl/",
            }

            response = requests.get(url, stream=True, timeout=30, headers=headers)
            response.raise_for_status()

            # Save to folder
            file_path = folder_path / original_name

            with open(file_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            file_size = file_path.stat().st_size
            self.logger.info(
                f"✅ Downloaded {file_type}: {original_name} ({file_size:,} bytes)"
            )

            return {
                "success": True,
                "type": file_type,
                "filename": original_name,
                "path": str(file_path),
                "size": file_size,
                "url": url,
            }

        except requests.RequestException as e:
            self.logger.error(f"❌ Download failed for {file_type}: {str(e)}")
            return {
                "success": False,
                "type": file_type,
                "error": str(e),
                "url": url if "url" in locals() else "unknown",
            }

        except Exception as e:
            self.logger.error(f"❌ Unexpected error downloading {file_type}: {str(e)}")
            return {
                "success": False,
                "type": file_type,
                "error": str(e),
                "url": url if "url" in locals() else "unknown",
            }

    async def handle_emission_attachment(self, file_info, folder_path):
        """Handle emission attachment downloads with _emis suffix"""
        try:
            url = file_info.get("url")
            original_name = file_info.get(
                "name", f"emission_{file_info.get('row', 'unknown')}.mp4"
            )

            if not url:
                return {
                    "success": False,
                    "type": "emission_attachment",
                    "error": "No URL provided",
                }

            # Check if acceptance file with same name exists
            acceptance_files = list(folder_path.glob(f"*{original_name}*"))
            final_name = original_name

            if acceptance_files:
                # Add _emis suffix: file.mp4 → file_emis.mp4
                name_parts = original_name.rsplit(".", 1)
                if len(name_parts) == 2:
                    final_name = f"{name_parts[0]}_emis.{name_parts[1]}"
                else:
                    final_name = f"{original_name}_emis"

                self.logger.info(
                    f"📝 Adding suffix to avoid conflict: {original_name} → {final_name}"
                )

            # Download with proper headers (for cookies)
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "*/*",
                "Referer": "https://cradle.egplusww.pl/",
            }

            self.logger.info(f"⬇️ Downloading emission attachment: {final_name}")
            self.logger.info(f"   URL: {url}")

            response = requests.get(url, stream=True, timeout=30, headers=headers)
            response.raise_for_status()

            # Save with final name
            file_path = folder_path / final_name

            with open(file_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            file_size = file_path.stat().st_size
            self.logger.info(
                f"✅ Downloaded emission attachment: {final_name} ({file_size:,} bytes)"
            )

            return {
                "success": True,
                "type": "emission_attachment",
                "filename": final_name,
                "original_name": original_name,
                "path": str(file_path),
                "size": file_size,
                "url": url,
            }

        except Exception as e:
            self.logger.error(f"❌ Emission attachment download failed: {str(e)}")
            return {"success": False, "type": "emission_attachment", "error": str(e)}

    async def handle_network_emission_file(self, file_info, cradle_folder, cradle_id):
        """Handle emission files from network drives"""
        try:
            network_path = file_info.get("path")
            if not network_path:
                return {"success": False, "error": "No network path provided"}

            self.logger.info(f"🌐 Processing network path: {network_path}")

            # Clean and normalize path
            if network_path.startswith("/Volumes/"):
                # macOS network path
                search_path = network_path
            elif network_path.startswith("\\\\"):
                # Windows UNC path
                search_path = network_path.replace("\\", "/")
            else:
                search_path = network_path

            # Remove trailing slashes
            search_path = search_path.rstrip("/")

            # ✅ SCENARIO 1: The path is already an exact file
            if os.path.isfile(search_path):
                self.logger.info(f"✅ Exact file found at network path: {search_path}")
                filename = os.path.basename(search_path)
                destination = cradle_folder / filename

                self.logger.info(f"📁 Copying direct network file: {search_path} → {destination}")
                shutil.copy2(search_path, destination)

                file_size = destination.stat().st_size
                self.logger.info(f"✅ Direct network file copied: {filename} ({file_size:,} bytes)")

                return {
                    "success": True,
                    "type": "emission_network",
                    "filename": filename,
                    "path": str(destination),
                    "source": search_path,
                    "size": file_size,
                    "exact_match": True,
                }

            self.logger.info(f"🔍 Path is a directory or doesn't exist directly. Searching in: {search_path}")

            # Common video extensions
            extensions = ["mp4", "mov", "avi", "mkv", "mxf", "prores", "MOV", "MP4"]

            found_files = []

            # ✅ ROZSZERZONE WZORCE WYSZUKIWANIA - TO JEST GŁÓWNA ZMIANA!
            search_patterns = [
                # Bezpośrednio w folderze
                f"{search_path}/{cradle_id}*",  # 879712*
                f"{search_path}/_{cradle_id}*",  # _879712* ← NOWY!
                f"{search_path}/*{cradle_id}*",  # *879712* ← NOWY!
                f"{search_path}/{cradle_id}_*",  # 879712_* ← NOWY!
                f"{search_path}/_{cradle_id}_*",  # _879712_* ← NOWY!
                # W podfolderach
                f"{search_path}/*/{cradle_id}*",  # */879712*
                f"{search_path}/*/_{cradle_id}*",  # */_879712* ← NOWY!
                f"{search_path}/*/*{cradle_id}*",  # */*879712* ← NOWY!
                f"{search_path}/*/{cradle_id}_*",  # */879712_* ← NOWY!
                f"{search_path}/*/_{cradle_id}_*",  # */_879712_* ← NOWY!
                # Deep search (wszystkie poziomy)
                f"{search_path}/**/{cradle_id}*",  # **/879712*
                f"{search_path}/**/_{cradle_id}*",  # **/_879712* ← NOWY!
                f"{search_path}/**/*{cradle_id}*",  # **/*879712* ← NOWY!
                f"{search_path}/**/{cradle_id}_*",  # **/879712_* ← NOWY!
                f"{search_path}/**/_{cradle_id}_*",  # **/_879712_* ← NOWY!
            ]

            for pattern_base in search_patterns:
                for ext in extensions:
                    pattern = f"{pattern_base}.{ext}"
                    self.logger.info(f"🔍 Searching pattern: {pattern}")

                    try:
                        matches = glob.glob(pattern, recursive=True)
                        if matches:
                            found_files.extend(matches)
                            self.logger.info(
                                f"✅ Found {len(matches)} files with pattern: {pattern}"
                            )
                            # Log first few matches
                            for match in matches[:3]:
                                self.logger.info(f"   📄 {os.path.basename(match)}")
                            # ✅ Jeśli znalazł pliki, przerwij dalsze szukanie
                            break
                    except Exception as e:
                        self.logger.warning(
                            f"⚠️ Pattern search failed: {pattern} - {str(e)}"
                        )

                # ✅ Jeśli znalazł pliki w tym wzorcu, przerwij dalsze wzorce
                if found_files:
                    break

            # Remove duplicates and sort
            found_files = sorted(list(set(found_files)))

            if found_files:
                # Use first file (usually the main version)
                source_file = found_files[0]
                filename = os.path.basename(source_file)
                destination = cradle_folder / filename

                self.logger.info(f"📁 Copying from network: {source_file}")
                self.logger.info(f"📁 Destination: {destination}")

                # Copy file
                shutil.copy2(source_file, destination)

                file_size = destination.stat().st_size
                self.logger.info(
                    f"✅ Network file copied: {filename} ({file_size:,} bytes)"
                )

                return {
                    "success": True,
                    "type": "emission_network",
                    "filename": filename,
                    "path": str(destination),
                    "source": source_file,
                    "size": file_size,
                    "found_files_count": len(found_files),
                    "all_found_files": [
                        os.path.basename(f) for f in found_files[:5]
                    ],  # First 5 filenames
                }
            else:
                error_msg = f"No files found starting with {cradle_id} in {search_path}"
                self.logger.warning(f"❌ {error_msg}")

                # ✅ LEPSZE DEBUGOWANIE - List what's actually in the directory
                try:
                    if os.path.exists(search_path):
                        files_in_dir = [
                            f for f in os.listdir(search_path) if not f.startswith(".")
                        ][:10]
                        self.logger.info(
                            f"📂 Files in directory (first 10): {files_in_dir}"
                        )

                        # ✅ SPRAWDŹ CZY JEST JAKIŚ PLIK Z PODOBNYM ID
                        similar_files = [f for f in files_in_dir if cradle_id in f]
                        if similar_files:
                            self.logger.info(
                                f"🔍 Files containing '{cradle_id}': {similar_files}"
                            )

                    else:
                        self.logger.warning(
                            f"📂 Directory does not exist: {search_path}"
                        )
                except Exception as e:
                    self.logger.warning(f"📂 Cannot list directory: {str(e)}")

                return {
                    "success": False,
                    "error": error_msg,
                    "search_path": search_path,
                    "patterns_tried": len(search_patterns) * len(extensions),
                }

        except Exception as e:
            self.logger.error(f"❌ Network file error: {str(e)}")
            return {"success": False, "error": str(e)}

    async def handle_lucid_emission_file(self, file_info, cradle_folder, cradle_id):
        """
        Handle emission files accessible via LucidLink filespace.

        Strategy:
          1. Base paths to check:
             - /Volumes/egpluswarsaw/alfa/Electrolux/Sources/1. CAMPAIGNS
             - /Volumes/egpluswarsaw/alfa/AEG/Sources/CAMPAIGNS
          2. Find campaign folder whose name starts with job_number (| → _)
          3. Search within that campaign folder for files by Template ID
        """
        try:
            LUCID_BASES = [
                Path("/Volumes/egpluswarsaw/alfa/Electrolux/Sources/1. CAMPAIGNS"),
                Path("/Volumes/egpluswarsaw/alfa/AEG/Sources/CAMPAIGNS")
            ]
            VIDEO_EXTENSIONS = {".mp4", ".mov", ".mxf", ".prores", ".avi", ".mkv"}

            job_number_raw = file_info.get("jobNumber") or ""
            template_id = file_info.get("templateId") or ""

            # Convert job number: "26|00124" → "26_00124"
            job_prefix = job_number_raw.replace("|", "_").strip()

            self.logger.info(f"🔗 Lucid emission lookup — jobPrefix: '{job_prefix}', templateId: '{template_id}'")
            
            # Step 1: Verify base paths are mounted
            mounted_bases = [base for base in LUCID_BASES if base.exists()]
            if not mounted_bases:
                error = f"No Lucid volumes mounted. Checked: {[str(b) for b in LUCID_BASES]}"
                self.logger.error(f"❌ {error}")
                return {"success": False, "error": error}
            
            self.logger.info(f"📂 Mounted base paths: {[str(b) for b in mounted_bases]}")

            # Step 2: Find campaign folder by job number prefix
            campaign_folder = None
            if job_prefix:
                for base_path in mounted_bases:
                    self.logger.info(f"🔍 Checking base path for job prefix '{job_prefix}': {base_path.name}")
                    for folder in base_path.iterdir():
                        if folder.is_dir() and folder.name.startswith(job_prefix):
                            campaign_folder = folder
                            self.logger.info(f"✅ Found campaign folder: {folder.name} in {base_path.parent.parent.name}")
                            break
                    if campaign_folder:
                        break

            # Define search targets (either the specific campaign folder, or ALL mounted bases if fallback)
            search_targets = []
            if campaign_folder:
                search_targets = [campaign_folder]
            else:
                # Fallback: search by template_id across all campaigns (slower but safe)
                if template_id:
                    self.logger.warning(f"⚠️ Job prefix '{job_prefix}' not found. Falling back to Template ID search across all mounted campaigns.")
                    search_targets = mounted_bases
                else:
                    error = f"Campaign folder not found for job prefix '{job_prefix}' and no Template ID provided."
                    self.logger.error(f"❌ {error}")
                    return {"success": False, "error": error}

            # Step 3: Search for video file by Template ID (+ Lang code) inside targets
            template_id = file_info.get("templateId") or ""
            lang_code = file_info.get("langCode") or ""  # e.g. "IT", "FR", "DE"
            found_file = None
            search_patterns = []

            if template_id:
                if lang_code:
                    search_patterns = [
                        f"*{template_id}*{lang_code}*",    # exact lang version first
                        f"*{template_id}*{lang_code.lower()}*",  # lowercase variant
                        f"*{template_id}*",                # any language (fallback)
                        f"*{cradle_id}*{lang_code}*",      # fallback to cradle_id + lang_code
                        f"*{cradle_id}*",                  # fallback to cradle_id only
                    ]
                    self.logger.info(f"🌍 Lang code '{lang_code}' — will prefer *{template_id}*{lang_code}* pattern, fallback to *{cradle_id}*")
                else:
                    search_patterns = [
                        f"*{template_id}*",
                        f"{template_id}*",
                        f"*{cradle_id}*",                  # fallback
                        f"{cradle_id}*",                   # fallback
                    ]
            else:
                search_patterns = [f"*{cradle_id}*"]

            for target_folder in search_targets:
                for pattern in search_patterns:
                    self.logger.info(f"🔍 Searching in {target_folder.name} with pattern: {pattern}")
                    for match in target_folder.rglob(pattern):
                        if match.is_file() and match.suffix.lower() in VIDEO_EXTENSIONS:
                            found_file = match
                            self.logger.info(f"✅ Found Lucid emission file: {match.name}")
                            break
                    if found_file:
                        break
                if found_file:
                    break

            if not found_file:
                error = f"No video file found for templateId='{template_id}' in any matching campaign folder"
                self.logger.error(f"❌ {error}")
                # Log first few items for debugging
                try:
                    if search_targets:
                        items = [f.name for f in search_targets[0].iterdir() if not f.name.startswith(".")][:10]
                        self.logger.info(f"📂 Folder contents of {search_targets[0].name} (first 10): {items}")
                except Exception:
                    pass
                return {"success": False, "error": error}

            # Step 4: Copy file to cradle download folder
            destination = cradle_folder / found_file.name
            self.logger.info(f"📁 Copying Lucid file: {found_file} → {destination}")
            shutil.copy2(str(found_file), str(destination))

            file_size = destination.stat().st_size
            self.logger.info(f"✅ Lucid emission file copied: {found_file.name} ({file_size:,} bytes)")

            return {
                "success": True,
                "type": "emission_lucid",
                "filename": found_file.name,
                "path": str(destination),
                "source": str(found_file),
                "size": file_size,
                "campaign_folder": campaign_folder.name,
            }

        except Exception as e:
            self.logger.error(f"❌ Lucid emission file error: {str(e)}")
            return {"success": False, "error": str(e)}

    async def send_download_results(self, websocket, results):
        """Send download results back to extension"""
        import json

        message = {
            "action": "DOWNLOAD_RESULTS",
            "data": results,
            "timestamp": int(asyncio.get_event_loop().time() * 1000),
        }

        await websocket.send(json.dumps(message))
        self.logger.info(
            f"📤 Sent download results: {len(results['files_downloaded'])} files, {len(results['errors'])} errors"
        )

    async def _process_downloaded_file(self, result, cradle_folder, file_type):
        """
        Post-process downloaded file:
        1. Unzip if it's a zip file
        2. Rename with suffix (_akcept / _emis) if needed
        """
        try:
            file_path = Path(result["path"])
            filename = result["filename"]

            # 1. Handle ZIP files
            if filename.lower().endswith(".zip"):
                self.logger.info(f"📦 Detected ZIP file: {filename}")
                try:
                    with zipfile.ZipFile(file_path, "r") as zip_ref:
                        # Extract all
                        extract_path = cradle_folder / f"extracted_{file_type}"
                        zip_ref.extractall(extract_path)
                        self.logger.info(f"📦 Extracted to: {extract_path}")

                        # Find video file inside
                        video_extensions = {
                            ".mp4",
                            ".mov",
                            ".mxf",
                            ".avi",
                            ".mkv",
                            ".prores",
                        }
                        largest_video = None
                        largest_size = 0

                        for root, _, files in os.walk(extract_path):
                            for f in files:
                                if Path(f).suffix.lower() in video_extensions:
                                    full_path = Path(root) / f
                                    size = full_path.stat().st_size
                                    if size > largest_size:
                                        largest_size = size
                                        largest_video = full_path

                        if largest_video:
                            # Move video to main folder
                            new_path = cradle_folder / largest_video.name
                            shutil.move(str(largest_video), str(new_path))
                            self.logger.info(
                                f"✅ Extracted video moved to: {new_path.name}"
                            )

                            # Clean up zip and extract folder
                            # os.remove(file_path) # Optional: keep zip?
                            # shutil.rmtree(extract_path) # Optional: clean up

                            # Update result
                            file_path = new_path
                            filename = new_path.name
                            result["path"] = str(new_path)
                            result["filename"] = filename
                        else:
                            self.logger.warning(
                                "⚠️ No video file found in ZIP archive"
                            )

                except zipfile.BadZipFile:
                    self.logger.error("❌ Invalid ZIP file")

            return result

        except Exception as e:
            self.logger.error(f"❌ Post-processing failed: {str(e)}")
            return result
