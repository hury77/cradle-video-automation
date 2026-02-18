import os
import requests
import logging
from pathlib import Path
import asyncio
import glob
import shutil
import zipfile
import subprocess

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

            self.logger.info(f"📁 Processing files for CradleID: {cradle_id}")

            if not cradle_id:
                await self.send_error(websocket, "No CradleID provided")
                return

            # Create cradle folder
            cradle_folder = self.download_base_path / cradle_id
            cradle_folder.mkdir(parents=True, exist_ok=True)
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

            self.logger.info(f"🔍 Searching in: {search_path}")

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

    async def handle_check_files_download(self, websocket, data):
        """Handle download of QA Check Files (Master, Copy Deck, Adaptation)"""
        try:
            cradle_id = data.get("cradleId")
            template_id = data.get("templateId")
            files = data.get("files", {})

            # Create folder
            cradle_folder = self.download_base_path / cradle_id
            cradle_folder.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"📂 Check Files Folder: {cradle_folder}")

            results = {
                "cradle_id": cradle_id,
                "files_downloaded": [],
                "errors": []
            }

            # 1. Handle MASTER
            # Priority: Lucid Link (if provided) > Deep Search (fallback)
            
            master_info = files.get("master")
            master_found = False
            
            if master_info and master_info.get("type") == "lucid":
                lucid_url = master_info.get("url")
                self.logger.info(f"🔗 Received Lucid Link: {lucid_url}")
                
                # Convert lucid://host/share/path -> /Volumes/share/path
                # Example: lucid://egpluswarsaw/Projects/File.mov -> /Volumes/egpluswarsaw/Projects/File.mov
                
                try:
                    # Logic to convert lucid:// url to local path
                    # Format 1: lucid://domain/root/path/to/file -> /Volumes/domain/root/path/to/file (approx)
                    # Format 2 (User provided): lucid://alfa.egpluswarsaw/file/97:55453/preview%20files
                    
                    master_path = None
                    convertible = False

                    if "lucid://" in lucid_url:
                        # naive attempt to map to /Volumes
                        # Remove protocol
                        path_part = lucid_url.replace("lucid://", "")
                        
                        # Check for ID-based link which we likely can't resolve directly to a file path easily
                        if "/file/" in path_part and ":" in path_part:
                             self.logger.warning(f"⚠️ Lucid ID-based link detected: {lucid_url}. Cannot resolve to direct file path without API.")
                             self.logger.info("   Will proceed to Deep Search as fallback.")
                        else:
                             # Try mapping for standard path-like links
                             candidate_path = Path("/Volumes") / path_part
                             if candidate_path.exists():
                                 master_path = candidate_path
                                 convertible = True
                             else:
                                 # Try stripping domain? 
                                 # lucid://alfa.egpluswarsaw/Select/folder -> /Volumes/Select/folder ??
                                 # This is guessing.
                                 parts = path_part.split("/")
                                 if len(parts) > 1:
                                     candidate_path_2 = Path("/Volumes") / "/".join(parts[1:])
                                     if candidate_path_2.exists():
                                         master_path = candidate_path_2
                                         convertible = True

                    if convertible and master_path and master_path.exists():
                        self.logger.info(f"✅ Resolved Lucid Master Path: {master_path}")
                        
                        if master_path.is_file():
                             dest = cradle_folder / master_path.name
                             shutil.copy2(master_path, dest)
                             results["files_downloaded"].append("master")
                             master_found = True
                        elif master_path.is_dir():
                             self.logger.info(f"📂 Lucid link points to directory. Searching inside: {master_path}")
                             # Use the search worker but scoped to this directory!
                             # But _search_worker expects template_id. 
                             # We can just copy the best file from this dir.
                             # For now, let's fall back to search, but hint the search to look here? 
                             # Actually simple: if we have a folder, maybe we should just set it as a search root?
                             # For now let's skip complex logic and let Deep Search handle it, 
                             # BUT Deep Search is optimized to stop early, so it should be fine.
                             pass
                    else:
                        self.logger.warning(f"⚠️ Could not resolve Lucid URL to local file: {lucid_url}")

                except Exception as e:
                    self.logger.error(f"❌ Error handling Lucid link: {e}")

            # Fallback to Deep Search if no Lucid link worked
            if not master_found and template_id:
                self.logger.info(f"🔍 Falling back to Deep Search for TemplateID: {template_id}")
                
                found_master = await self._find_and_copy_master_file(
                    template_id, cradle_folder
                )
                
                if found_master["success"]:
                    results["files_downloaded"].append(found_master)
                else:
                    results["errors"].append(found_master)
                    
            elif not master_found and not template_id:
                results["errors"].append({"success": False, "type": "master", "error": "No Template ID and no valid Lucid link"})

            return results

        except Exception as e:
            self.logger.error(f"❌ handle_check_files_download error: {str(e)}")
            return {"error": str(e)}

    async def _find_and_copy_master_file(self, template_id, dest_folder):
        """Async wrapper for the blocking search worker"""
        if not template_id:
            return {"success": False, "type": "master", "error": "No Template ID provided"}

        loop = asyncio.get_event_loop()
        # Run blocking I/O in a separate thread
        return await loop.run_in_executor(None, self._search_worker, template_id, dest_folder)

    def _search_worker(self, template_id, dest_folder):
        """Synchronous worker for searching files (runs in thread)"""
        # 1. TRY SPOTLIGHT (mdfind) - Instant on macOS
        self.logger.info(f"🔍 [Spotlight] Searching for '{template_id}'...")
        try:
            # Search for the Folder matching the TemplateID
            # mdfind -name "TEMPLATE_ID" -onlyin /Volumes
            cmd = ["mdfind", "-name", template_id, "-onlyin", "/Volumes"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            spotlight_candidates = []
            if result.returncode == 0 and result.stdout:
                paths = result.stdout.strip().split('\n')
                self.logger.info(f"⚡ [Spotlight] Found {len(paths)} matches.")
                
                for p_str in paths:
                    p = Path(p_str)
                    # We are looking for the FOLDER matching the ID, or a file inside it
                    # If p is the folder "260105KCLJ", we look inside
                    if p.is_dir() and p.name == template_id:
                        self.logger.info(f"   📂 [Spotlight] Found matching directory: {p}")
                        # Look inside this folder for files
                        sub_files = []
                        sub_files.extend(p.glob("*"))
                        sub_files.extend(p.glob("*/*"))
                        
                        for sf in sub_files:
                            if sf.is_file() and not sf.name.startswith("."):
                                spotlight_candidates.append(sf)
                    
                    elif p.is_file() and template_id in p.name:
                        # Found a file directly
                         spotlight_candidates.append(p)
            
            if spotlight_candidates:
                self.logger.info(f"   ✅ [Spotlight] Found {len(spotlight_candidates)} candidate files via Spotlight.")
                return self._process_candidates(spotlight_candidates, template_id, dest_folder)
            else:
                 self.logger.info("   ⚠️ [Spotlight] No matches found. Falling back to simple scan...")

        except Exception as e:
            self.logger.error(f"❌ [Spotlight] Error: {e}")

        # 2. FALLBACK: Native 'find' command (Faster than os.walk)
        self.logger.info(f"🔍 [Fallback] Using native 'find' command to locate directory '{template_id}'...")
        
        try:
            # Optimize: Search specific deep paths first if they exist, then root
            search_paths = []
            
            # 1. Specifc high-probability paths
            specific_path = Path("/Volumes/egpluswarsaw/alfa/Electrolux/Sources/1. CAMPAIGNS")
            if specific_path.exists():
                search_paths.append(str(specific_path))
            
            # 2. General Volume root
            search_paths.append("/Volumes")

            found_dir = None
            
            for search_path in search_paths:
                self.logger.info(f"   Searching in: {search_path}")
                # find PATH -name "TEMPLATE_ID" -type d -print -quit
                cmd = ["find", search_path, "-name", template_id, "-type", "d", "-maxdepth", "8", "-print", "-quit"]
                
                try:
                    # Increased timeout to 120s for network drives
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                    if result.returncode == 0 and result.stdout:
                        found_dir = result.stdout.strip()
                        if found_dir: break # Found it!
                except subprocess.TimeoutExpired:
                     self.logger.warning(f"   ⚠️ [find] Timeout in {search_path}")
                     continue

            if found_dir:
                self.logger.info(f"✅ [find] Directory located: {found_dir}")
                p = Path(found_dir)
                
                # Search inside this directory nicely
                candidates = []
                sub_files = []
                sub_files.extend(p.glob("*"))
                sub_files.extend(p.glob("*/*"))
                
                for sf in sub_files:
                    if sf.is_file() and not sf.name.startswith("."):
                        candidates.append(sf)
                
                if candidates:
                    self.logger.info(f"   Files found inside: {len(candidates)}")
                    return self._process_candidates(candidates, template_id, dest_folder)

            
            self.logger.info("   ⚠️ [find] No directory found.")

        except subprocess.TimeoutExpired:
            self.logger.warning("⚠️ [find] Search timed out after 30s")
        except Exception as e:
            self.logger.error(f"❌ [find] Error: {e}")

        return {"success": False, "type": "master", "error": "File not found (Search exhausted)"}




    def _process_candidates(self, candidates, template_id, dest_folder):
            # Filtering and Scoring Logic
            # 1. Exact match file > File inside matched folder
            # 2. "Master" in name > "Clean" in name > other
            # 3. Extensions: pdf, ai, psd, indd, zip > jpg, png

            scored_candidates = []
            priority_exts = [".pdf", ".ai", ".psd", ".indd", ".zip", ".mov", ".mp4", ".jpg", ".jpeg", ".png"]
            
            for cand in candidates:
                score = 0
                name_lower = cand.name.lower()
                
                if template_id in cand.name: score += 100
                if "master" in name_lower: score += 50
                if cand.suffix.lower() in priority_exts: score += 20
                if "preview" in name_lower or "thumb" in name_lower: score -= 50
                
                scored_candidates.append((score, cand))
            
            scored_candidates.sort(key=lambda x: x[0], reverse=True)
            
            if not scored_candidates:
                return {"success": False, "type": "master", "error": "No suitable candidates found"}

            best_candidate = scored_candidates[0][1]
            self.logger.info(f"✅ Best Candidate: {best_candidate} (Score: {scored_candidates[0][0]})")

            dest_path = dest_folder / best_candidate.name
            shutil.copy2(best_candidate, dest_path)

            return {
                "success": True,
                "type": "master",
                "path": str(dest_path),
                "original_path": str(best_candidate),
                "size": dest_path.stat().st_size
            }


