import asyncio
import websockets
import json
import logging
from file_handler import FileHandler
from video_compare_automator import VideoCompareAutomator
from api_client import APIClient
import time
import shutil
import os
from pathlib import Path
from zip_utils import check_and_unzip_folder

logger = logging.getLogger(__name__)




class WebSocketServer:
    def __init__(self):
        self.clients = set()
        self.file_handler = FileHandler()
        self.video_compare = VideoCompareAutomator()
        self.api_client = APIClient()

    async def register(self, websocket):
        """Register a new client"""
        self.clients.add(websocket)
        logger.info(f"Client connected. Total clients: {len(self.clients)}")

    async def unregister(self, websocket):
        """Unregister a client"""
        self.clients.discard(websocket)
        logger.info(f"Client disconnected. Total clients: {len(self.clients)}")

    async def handle_client(self, websocket, path):
        """Handle individual client connection"""
        await self.register(websocket)
        try:
            async for message in websocket:
                await self.handle_message(websocket, message)
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            logger.error(f"Error handling client: {str(e)}")
        finally:
            await self.unregister(websocket)

    async def handle_message(self, websocket, message):
        """Handle incoming messages from clients"""
        try:
            logger.info(f"Received: {message}")
            data = json.loads(message)
            action = data.get("action")

            if action == "extension_connected":
                logger.info("Extension connected")
                await self.send_response(
                    websocket, "CONNECTION_ESTABLISHED", {"status": "connected"}
                )

            elif action == "FILES_DETECTED":
                logger.info("🎯 FILES_DETECTED received - starting download process...")
                await self.handle_files_detected(websocket, data)

            elif action == "VIDEO_COMPARE_REQUEST":
                logger.info(
                    "🎬 VIDEO_COMPARE_REQUEST received - starting Video Compare..."
                )
                await self.handle_video_compare_request(websocket, data)

            elif action == "VIDEO_COMPARE_API_REQUEST":
                logger.info(
                    "🚀 VIDEO_COMPARE_API_REQUEST received - starting Direct API Compare..."
                )
                await self.handle_video_compare_api_request(websocket, data)

            elif action == "VIDEO_COMPARE_UPLOAD_REQUEST":
                logger.info(
                    "🎬 VIDEO_COMPARE_UPLOAD_REQUEST received - hybrid upload..."
                )
                await self.handle_video_compare_upload_request(websocket, data)

            elif action == "TASK_SCAN_REQUEST":
                logger.info("📋 TASK_SCAN_REQUEST received")
                await self.handle_task_scan_request(websocket, data)

            elif action == "AUTOMATION_STATUS_REQUEST":
                logger.info("📊 AUTOMATION_STATUS_REQUEST received")
                await self.handle_automation_status_request(websocket, data)

            elif action == "PING":
                logger.info("📡 PING received")
                await self.send_response(
                    websocket, "PONG", {"timestamp": int(time.time() * 1000)}
                )

            elif action == "MOVE_DOWNLOADED_FILE":
                logger.info("📦 MOVE_DOWNLOADED_FILE received")
                await self.handle_move_file(websocket, data)

            else:
                logger.warning(f"Unknown action: {action}")
                await self.send_error(websocket, f"Unknown action: {action}")

        except json.JSONDecodeError:
            logger.error(f"Invalid JSON received: {message}")
            await self.send_error(websocket, "Invalid JSON format")
        except Exception as e:
            logger.error(f"Error handling message: {str(e)}")
            await self.send_error(websocket, f"Server error: {str(e)}")

    async def handle_move_file(self, websocket, data):
        """Move a blob-downloaded file from Downloads root into cradleId subfolder, then unzip if needed"""
        try:
            filename = data.get("filename")
            cradle_id = data.get("cradleId")
            
            if not filename or not cradle_id:
                await self.send_error(websocket, "Missing filename or cradleId")
                return
            
            downloads_dir = Path.home() / "Downloads"
            target_dir = downloads_dir / cradle_id
            target_dir.mkdir(parents=True, exist_ok=True)

            # Chrome Downloads API saves directly to subfolder (961143/file.zip)
            # Blob fallback saves to Downloads root, then we move it
            already_in_subfolder = (target_dir / filename).exists()
            source = downloads_dir / filename      # blob fallback path
            target = target_dir / filename

            if already_in_subfolder:
                logger.info(f"📦 File already in subfolder (Chrome API): {cradle_id}/{filename}")
            else:
                # Retry move from Downloads root
                for attempt in range(10):
                    if source.exists():
                        shutil.move(str(source), str(target))
                        logger.info(f"📦 Moved: {filename} → {cradle_id}/{filename}")
                        break
                    await asyncio.sleep(1)
                else:
                    logger.warning(f"⚠️ File not found after retries: {source}")
                    await self.send_error(websocket, f"File not found: {filename}")
                    return


            # Unzip if it's a ZIP file
            final_filename = filename
            if filename.lower().endswith(".zip") and target.exists():
                logger.info(f"📦 Unzipping: {filename}")
                try:
                    import zipfile
                    with zipfile.ZipFile(target, "r") as zip_ref:
                        extract_dir = target_dir / "_extracted_tmp"
                        zip_ref.extractall(extract_dir)
                        
                        # Find largest video file
                        video_exts = {".mp4", ".mov", ".mxf", ".avi", ".mkv", ".prores"}
                        largest_video = None
                        largest_size = 0
                        
                        for root, _, files in os.walk(extract_dir):
                            for f in files:
                                if Path(f).suffix.lower() in video_exts:
                                    fpath = Path(root) / f
                                    fsize = fpath.stat().st_size
                                    if fsize > largest_size:
                                        largest_size = fsize
                                        largest_video = fpath
                        
                        if largest_video:
                            video_dest = target_dir / largest_video.name
                            shutil.move(str(largest_video), str(video_dest))
                            final_filename = largest_video.name
                            logger.info(f"✅ Extracted video: {final_filename} ({largest_size:,} bytes)")
                            
                            # Cleanup ZIP and temp folder
                            os.remove(target)
                            shutil.rmtree(extract_dir, ignore_errors=True)
                            logger.info(f"🗑️ Cleaned up ZIP and temp folder")
                        else:
                            logger.warning("⚠️ No video found in ZIP, keeping archive")
                            shutil.rmtree(extract_dir, ignore_errors=True)
                            
                except Exception as e:
                    logger.error(f"❌ Unzip failed: {str(e)}")

            await self.send_response(websocket, "FILE_MOVED", {
                "filename": final_filename,
                "destination": str(target_dir / final_filename)
            })
            
        except Exception as e:
            logger.error(f"❌ Move file error: {str(e)}")
            await self.send_error(websocket, f"Move error: {str(e)}")

    async def handle_files_detected(self, websocket, data):
        """Handle FILES_DETECTED message - download files"""
        try:
            cradle_id = data.get("cradleId")
            acceptance_file = data.get("acceptanceFile")
            emission_file = data.get("emissionFile")

            if not cradle_id:
                await self.send_error(websocket, "No CradleID provided")
                return

            logger.info(f"📁 Processing files for CradleID: {cradle_id}")

            # Send status update
            await self.send_status_update(
                websocket,
                "DOWNLOAD_STARTED",
                {
                    "cradle_id": cradle_id,
                    "status": "Starting file downloads...",
                    "acceptance_file": acceptance_file,
                    "emission_file": emission_file,
                },
            )

            # Handle file downloads via FileHandler
            download_results = await self.file_handler.handle_files_detected(
                websocket, data
            )

            # Send completion status
            await self.send_status_update(
                websocket,
                "DOWNLOAD_COMPLETED",
                {
                    "cradle_id": cradle_id,
                    "results": download_results,
                    "status": "File downloads completed",
                },
            )

        except Exception as e:
            logger.error(f"❌ Files detected handling failed: {str(e)}")
            await self.send_error(websocket, f"File download error: {str(e)}")

    async def handle_video_compare_request(self, websocket, data):
        """Handle Video Compare automation request"""
        try:
            cradle_id = data.get("cradleId")

            if not cradle_id:
                await self.send_error(
                    websocket, "No CradleID provided for Video Compare"
                )
                return

            # Build file paths
            base_path = Path.home() / "Downloads" / cradle_id
            logger.info(f"🔍 Looking for files in: {base_path}")

            # Find acceptance and emission files
            acceptance_file = None
            emission_file = None

            if base_path.exists():
                # ✅ AUTO-UNZIP: Rozpakuj ewentualne ZIPy przed szukaniem wideo
                zip_result = check_and_unzip_folder(base_path)
                if zip_result['processed_zips'] > 0:
                    logger.info(f"📦 Auto-unzipped {zip_result['processed_zips']} archives in {cradle_id}")
                    if zip_result['errors']:
                        logger.error(f"❌ ZIP Errors: {zip_result['errors']}")

                files = list(base_path.glob("*"))
                logger.info(
                    f"📁 Files in {cradle_id} folder: {[f.name for f in files]}"
                )
                logger.info(f"📊 Total files found: {len(files)}")

                # ✅ ZBIERZ WSZYSTKIE PLIKI WIDEO
                video_files = []
                video_extensions = [
                    ".mp4",
                    ".mov",
                    ".mxf",
                    ".prores",
                    ".avi",
                    ".mkv",
                    ".MP4",
                    ".MOV",
                    ".MXF",
                    ".PRORES",
                    ".AVI",
                    ".MKV",
                ]

                for file_path in files:
                    if file_path.is_file():
                        file_size = file_path.stat().st_size
                        logger.info(
                            f"🔍 Analyzing file: {file_path.name} ({file_size} bytes)"
                        )

                        # Sprawdź czy to plik wideo
                        if any(
                            file_path.name.endswith(ext) for ext in video_extensions
                        ):
                            video_files.append(file_path)
                            logger.info(f"✅ Video file detected: {file_path.name}")
                        else:
                            logger.info(f"⚠️ File ignored (not video): {file_path.name}")

                logger.info(f"📹 Found {len(video_files)} video files total")

                # ✅ INTELIGENTNE ROZRÓŻNIENIE PLIKÓW
                if len(video_files) >= 2:
                    acceptance_file, emission_file = await self.identify_video_files(
                        video_files, cradle_id
                    )

                elif len(video_files) == 1:
                    logger.warning(f"⚠️ Only 1 video file found, need 2 for comparison")
                    await self.send_error(
                        websocket,
                        f"Only 1 video file found in {cradle_id} folder, need 2 for comparison. Found: {video_files[0].name}",
                    )
                    return

                else:
                    logger.error(f"❌ No video files found in {cradle_id} folder")
                    await self.send_error(
                        websocket,
                        f"No video files found in {cradle_id} folder. Found files: {[f.name for f in files]}",
                    )
                    return

                # ✅ DODATKOWE LOGOWANIE WYNIKÓW
                logger.info(f"📋 === FILE DETECTION RESULTS ===")
                logger.info(
                    f"   Acceptance file: {Path(acceptance_file).name if acceptance_file else 'NOT FOUND'}"
                )
                logger.info(
                    f"   Acceptance size: {Path(acceptance_file).stat().st_size / 1024 / 1024:.1f} MB"
                    if acceptance_file
                    else "N/A"
                )
                logger.info(
                    f"   Emission file: {Path(emission_file).name if emission_file else 'NOT FOUND'}"
                )
                logger.info(
                    f"   Emission size: {Path(emission_file).stat().st_size / 1024 / 1024:.1f} MB"
                    if emission_file
                    else "N/A"
                )
                logger.info(f"📋 === END DETECTION RESULTS ===")

            else:
                logger.error(f"❌ Folder does not exist: {base_path}")
                await self.send_error(websocket, f"Folder not found: {cradle_id}")
                return

            # ✅ SPRAWDŹ CZY ZNALEZIONO OBA PLIKI
            if not acceptance_file or not emission_file:
                missing_files = []
                if not acceptance_file:
                    missing_files.append("acceptance file")
                if not emission_file:
                    missing_files.append("emission file")

                error_msg = f"Missing files in {cradle_id} folder. Missing: {', '.join(missing_files)}. Found video files: {[f.name for f in video_files] if 'video_files' in locals() else 'No video files'}"
                logger.error(f"❌ {error_msg}")
                await self.send_error(websocket, error_msg)
                return

            logger.info(f"🎬 Starting Video Compare automation for {cradle_id}")
            logger.info(f"   📁 Acceptance: {Path(acceptance_file).name}")
            logger.info(f"   📁 Emission: {Path(emission_file).name}")

            # Send status update
            await self.send_status_update(
                websocket,
                "VIDEO_COMPARE_STARTED",
                {
                    "cradle_id": cradle_id,
                    "status": "Starting Video Compare automation...",
                    "acceptance_file": Path(acceptance_file).name,
                    "emission_file": Path(emission_file).name,
                },
            )

            # ✅ POPRAWKA: USUNIĘTO CRADLE_ID Z ARGUMENTÓW
            result = await self.video_compare.upload_videos(
                acceptance_file, emission_file
            )

            # Send results
            await self.send_video_compare_results(websocket, result)

        except Exception as e:
            logger.error(f"❌ Video Compare request failed: {str(e)}")
            await self.send_error(websocket, f"Video Compare error: {str(e)}")

    async def handle_video_compare_upload_request(self, websocket, data):
        """Handle hybrid Video Compare upload request from extension"""
        try:
            cradle_id = data.get("cradleId")
            tab_id = data.get("tabId")
            selectors = data.get("selectors", {})

            if not cradle_id:
                await self.send_error(
                    websocket, "No CradleID provided for hybrid upload"
                )
                return

            # Build file paths
            base_path = Path.home() / "Downloads" / cradle_id
            logger.info(f"🔍 Looking for files for hybrid upload in: {base_path}")

            if not base_path.exists():
                await self.send_error(
                    websocket, f"Folder not found for hybrid upload: {cradle_id}"
                )
                return

            files = list(base_path.glob("*"))
            video_files = []
            video_extensions = [".mp4", ".mov", ".mxf", ".prores", ".avi", ".mkv"]

            for file_path in files:
                if file_path.is_file() and any(
                    file_path.name.lower().endswith(ext) for ext in video_extensions
                ):
                    video_files.append(file_path)

            if len(video_files) < 2:
                await self.send_error(
                    websocket,
                    f"Need 2 video files for comparison, found {len(video_files)}",
                )
                return

            # Identify acceptance and emission files
            acceptance_file, emission_file = await self.identify_video_files(
                video_files, cradle_id
            )

            if not acceptance_file or not emission_file:
                await self.send_error(
                    websocket, "Could not identify acceptance and emission files"
                )
                return

            logger.info(f"🎬 Starting hybrid Video Compare upload for {cradle_id}")
            logger.info(f"   📁 Acceptance: {Path(acceptance_file).name}")
            logger.info(f"   📁 Emission: {Path(emission_file).name}")

            # ✅ POPRAWKA: UŻYWAMY handle_hybrid_upload ZAMIAST upload_videos
            result = await self.video_compare.handle_hybrid_upload(
                acceptance_file, emission_file, cradle_id
            )

            # Send results back to extension
            await self.send_video_compare_results(websocket, result)

        except Exception as e:
            logger.error(f"❌ Hybrid Video Compare upload failed: {str(e)}")
            await self.send_error(websocket, f"Hybrid upload error: {str(e)}")

    async def handle_video_compare_api_request(self, websocket, data):
        """Handle Video Compare request via Direct API (Parallel Implementation)"""
        try:
            cradle_id = data.get("cradleId")
            
            if not cradle_id:
                await self.send_error(websocket, "No CradleID provided for API Compare")
                return

            # Build file paths (reuse existing logic from file_handler/server)
            base_path = Path.home() / "Downloads" / cradle_id
            logger.info(f"🔍 [API] Looking for files in: {base_path}")
            
            if not base_path.exists():
                await self.send_error(websocket, f"Folder not found: {cradle_id}")
                return

            # ✅ AUTO-UNZIP: Rozpakuj ewentualne ZIPy przed szukaniem wideo
            zip_result = check_and_unzip_folder(base_path)
            if zip_result['processed_zips'] > 0:
                logger.info(f"📦 [API] Auto-unzipped {zip_result['processed_zips']} archives in {cradle_id}")
                if zip_result['errors']:
                    logger.error(f"❌ [API] ZIP Errors: {zip_result['errors']}")

            files = list(base_path.glob("*"))
            video_files = [f for f in files if f.suffix.lower() in [".mp4", ".mov", ".mxf", ".prores", ".avi", ".mkv"]]
            
            if len(video_files) < 2:
                await self.send_error(websocket, f"Need 2 video files, found {len(video_files)}")
                return

            # Identify files
            acceptance_path, emission_path = await self.identify_video_files(video_files, cradle_id)
            
            if not acceptance_path or not emission_path:
                await self.send_error(websocket, "Could not identify acceptance and emission files")
                return

            # ────────── DUPLICATE CHECK ──────────
            try:
                existing_jobs = await self.api_client.get_jobs_by_cradle_id(cradle_id)
                acc_name = Path(acceptance_path).name
                emi_name = Path(emission_path).name
                
                for job in existing_jobs:
                    status = job.get("status")
                    
                    # 1. If job is already running or pending - STOP
                    if status in ["pending", "processing"]:
                        logger.info(f"🚫 [API] Skipping job for {cradle_id} - Job {job['id']} already in progress ({status})")
                        await self.send_response(websocket, "VIDEO_COMPARE_RESULTS", {
                            "success": True,
                            "job_id": job["id"],
                            "message": f"Job for {cradle_id} is already in progress ({status}). Reusing existing job ID.",
                            "is_duplicate": True
                        })
                        return

                    # 2. If job is completed - check if files are the same
                    if status == "completed":
                        # Check if original filenames match
                        # (job["filename"] has a unique suffix, but original_name is the one from disk)
                        job_acc_orig = job.get("acceptance_file", {}).get("original_name")
                        job_emi_orig = job.get("emission_file", {}).get("original_name")
                        
                        if job_acc_orig == acc_name and job_emi_orig == emi_name:
                            logger.info(f"🚫 [API] Skipping job for {cradle_id} - Identical original files already compared (Job {job['id']})")
                            await self.send_response(websocket, "VIDEO_COMPARE_RESULTS", {
                                "success": True,
                                "job_id": job["id"],
                                "message": f"Identical comparison for {cradle_id} was already completed. Reusing results.",
                                "is_duplicate": True
                            })
                            return
            except Exception as e:
                logger.warning(f"⚠️ [API] Failed to check for existing jobs: {str(e)}")
            # ──────────────────────────────────────

            logger.info(f"🚀 [API] Starting API Job for {cradle_id}")
            logger.info(f"   📂 Acceptance: {acc_name}")
            logger.info(f"   📂 Emission: {emi_name}")

            # Send status: Started
            await self.send_status_update(websocket, "VIDEO_COMPARE_STARTED", {
                "cradle_id": cradle_id,
                "status": "Uploading files to API...",
                "mode": "API_CLIENT"
            })

            # 1. Upload Acceptance
            acc_result = await self.api_client.upload_file(acceptance_path, "acceptance", cradle_id)
            if not acc_result or "file_id" not in acc_result:
                raise Exception(f"Acceptance upload failed: {acc_result}")
            
            # 2. Upload Emission
            emi_result = await self.api_client.upload_file(emission_path, "emission", cradle_id)
            if not emi_result or "file_id" not in emi_result:
                 raise Exception(f"Emission upload failed: {emi_result}")

            # 3. Create Job
            client_name = data.get("clientName") or data.get("client_name")
            job_result = await self.api_client.create_comparison_job(
                acceptance_id=acc_result["file_id"],
                emission_id=emi_result["file_id"],
                cradle_id=cradle_id,
                job_name=f"Auto-Compare {cradle_id}",
                client_name=client_name,
                comparison_type="automation"
            )

            if not job_result or "id" not in job_result:
                 raise Exception(f"Job creation failed: {job_result}")

            logger.info(f"✅ [API] Job started successfully: ID {job_result['id']}")

            # Send status update that job has started
            await self.send_status_update(websocket, "VIDEO_COMPARE_PROCESSING", {
                "cradle_id": cradle_id,
                "status": f"Job {job_result['id']} is processing on backend...",
                "job_id": job_result["id"]
            })
            
            # Poll for job completion to avoid opening 100 simultaneous jobs
            job_id = job_result["id"]
            job_finished = False
            final_status = None
            final_res = None
            
            for attempt in range(120): # Max 10 minutes
                await asyncio.sleep(5)
                status_res = await self.api_client.get_job_status(job_id)
                
                if isinstance(status_res, dict) and "status" in status_res:
                    current = status_res.get("status")
                    logger.info(f"⏳ [API] Job {job_id} processing... Status: {current}")
                    
                    if current.upper() in ["COMPLETED", "FAILED", "ERROR"]:
                        job_finished = True
                        final_status = current.upper()
                        final_res = status_res
                        break
                    
                    # Send continuous progress update to extension
                    progress = status_res.get("progress", 0)
                    msg = f"Processing video... {current} ({attempt*5}s) - {progress}%"
                    await self.send_status_update(websocket, "PROCESSING", {"message": msg, "progress": progress})
            
            if not job_finished:
                 logger.error(f"❌ [API] Job {job_id} timed out waiting for completion")
                 raise Exception("Timeout waiting for job completion")
                 
            logger.info(f"✅ [API] Job {job_id} finished with status: {final_status}")

            # Send actual final results
            await self.send_video_compare_results(websocket, {
                "success": final_status == "COMPLETED",
                "job_id": job_id,
                "message": f"Job finished with status: {final_status}",
                "api_response": final_res
            })

            # Open results in browser silently or if requested (Optional - commented out to avoid tab spam during automation)
            # import webbrowser
            # results_url = f"http://localhost:3000/compare/{job_id}"
            # logger.info(f"🌍 Opening results in browser: {results_url}")
            # webbrowser.open(results_url)

        except Exception as e:
            logger.error(f"❌ [API] Error: {str(e)}")
            await self.send_error(websocket, f"API Error: {str(e)}")

    async def identify_video_files(self, video_files, cradle_id):
        """Intelligently identify acceptance and emission files"""
        acceptance_file = None
        emission_file = None

        # ─────────────────────────────────────────────
        # Metoda 0: _emis sufiks — NAJPEWNIEJSZY WYRÓŻNIK
        # Extension zawsze dodaje _emis do pobranych plików emisji.
        # ─────────────────────────────────────────────
        for video_file in video_files:
            file_name_lower = video_file.name.lower()
            if "_emis." in file_name_lower or file_name_lower.endswith("_emis"):
                emission_file = str(video_file)
                logger.info(f"✅ [M0] Identified as EMISSION (_emis suffix): {video_file.name}")
            elif not acceptance_file:
                acceptance_file = str(video_file)
                logger.info(f"✅ [M0] Identified as ACCEPTANCE (no _emis): {video_file.name}")

        if acceptance_file and emission_file:
            logger.info("✅ [M0] Both files identified by _emis suffix — skipping heuristics")
            return acceptance_file, emission_file

        # Reset — fallback to heuristics
        acceptance_file = None
        emission_file = None

        # ─────────────────────────────────────────────
        # Metoda 1: Wzorce nazwy i rozmiar
        # ─────────────────────────────────────────────
        for video_file in video_files:
            file_name_lower = video_file.name.lower()
            file_size = video_file.stat().st_size

            logger.info(f"🔍 Analyzing for identification: {video_file.name}")
            logger.info(
                f"   Size: {file_size} bytes ({file_size / 1024 / 1024:.1f} MB)"
            )

            # Acceptance: pliki z określonymi wzorcami lub mniejsze pliki
            if not acceptance_file:
                acceptance_patterns = [
                    "accept",
                    "approval",
                    "qa",
                    "proof",
                    "wcy",
                    "_w" + cradle_id[-3:].lower(),
                ]

                is_acceptance = any(
                    pattern in file_name_lower for pattern in acceptance_patterns
                ) or (
                    file_name_lower.endswith(".mp4") and file_size < 300_000_000
                )  # < 300MB dla .mp4

                if is_acceptance:
                    acceptance_file = str(video_file)
                    logger.info(f"✅ [M1] Identified as ACCEPTANCE: {video_file.name}")
                    continue

            # Emission: pliki z określonymi wzorcami lub większe pliki
            if not emission_file:
                emission_patterns = [
                    "emission",
                    "broadcast",
                    "final",
                    "_1.",
                    "_final",
                    "master",
                ]

                is_emission = (
                    any(pattern in file_name_lower for pattern in emission_patterns)
                    or file_name_lower.endswith(".mov")
                    or file_name_lower.endswith(".mxf")
                    or file_name_lower.endswith(".prores")
                    or (file_size > 300_000_000)  # > 300MB
                )

                if is_emission:
                    emission_file = str(video_file)
                    logger.info(f"✅ [M1] Identified as EMISSION: {video_file.name}")
                    continue

        # ─────────────────────────────────────────────
        # Metoda 2: Rozmiar (mniejszy = acceptance, większy = emission)
        # ─────────────────────────────────────────────
        if not acceptance_file or not emission_file:
            logger.info(
                "⚠️ Could not identify files by pattern, using size and order..."
            )
            video_files_by_size = sorted(video_files, key=lambda x: x.stat().st_size)

            if not acceptance_file and len(video_files_by_size) > 0:
                acceptance_file = str(video_files_by_size[0])
                logger.info(
                    f"✅ [M2] Assigned as ACCEPTANCE (smallest): {video_files_by_size[0].name}"
                )

            if not emission_file and len(video_files_by_size) > 1:
                for vf in reversed(video_files_by_size):
                    if str(vf) != acceptance_file:
                        emission_file = str(vf)
                        logger.info(f"✅ [M2] Assigned as EMISSION (largest): {vf.name}")
                        break

        # ─────────────────────────────────────────────
        # Metoda 3: Alfabetyczna — ostatnia szansa
        # ─────────────────────────────────────────────
        if not acceptance_file or not emission_file:
            logger.info("⚠️ Still missing files, using alphabetical order...")
            video_files_sorted = sorted(video_files, key=lambda x: x.name.lower())

            if not acceptance_file and len(video_files_sorted) > 0:
                acceptance_file = str(video_files_sorted[0])
                logger.info(
                    f"✅ [M3] Assigned as ACCEPTANCE (alphabetically first): {video_files_sorted[0].name}"
                )

            if not emission_file and len(video_files_sorted) > 1:
                for vf in video_files_sorted:
                    if str(vf) != acceptance_file:
                        emission_file = str(vf)
                        logger.info(
                            f"✅ [M3] Assigned as EMISSION (alphabetically second): {vf.name}"
                        )
                        break

        return acceptance_file, emission_file


    async def handle_task_scan_request(self, websocket, data):
        """Handle task scanning requests"""
        try:
            scan_type = data.get("scanType", "pending_tasks")

            logger.info(f"📋 Processing task scan request: {scan_type}")

            # Send acknowledgment
            await self.send_status_update(
                websocket,
                "TASK_SCAN_STARTED",
                {
                    "scan_type": scan_type,
                    "status": "Task scanning started...",
                    "timestamp": int(time.time() * 1000),
                },
            )

            # Simulate task scanning (replace with actual implementation)
            await asyncio.sleep(2)

            # Mock results
            scan_results = {
                "found_tasks": 3,
                "pending_tasks": 2,
                "processing_tasks": 1,
                "scan_timestamp": int(time.time() * 1000),
            }

            await self.send_response(
                websocket,
                "TASK_SCAN_RESULTS",
                {
                    "scan_type": scan_type,
                    "results": scan_results,
                    "status": "Task scan completed",
                },
            )

        except Exception as e:
            logger.error(f"❌ Task scan failed: {str(e)}")
            await self.send_error(websocket, f"Task scan error: {str(e)}")

    async def handle_automation_status_request(self, websocket, data):
        """Handle automation status requests"""
        try:
            logger.info("📊 Processing automation status request")

            # Collect status information
            status_info = {
                "server_status": "running",
                "connected_clients": len(self.clients),
                "file_handler_ready": self.file_handler is not None,
                "video_compare_ready": self.video_compare is not None,
                "timestamp": int(time.time() * 1000),
            }

            await self.send_response(
                websocket,
                "AUTOMATION_STATUS",
                {"status": status_info, "message": "Automation system operational"},
            )

        except Exception as e:
            logger.error(f"❌ Status request failed: {str(e)}")
            await self.send_error(websocket, f"Status request error: {str(e)}")

    async def send_video_compare_results(self, websocket, result):
        """Send Video Compare results to extension"""
        message = {
            "action": "VIDEO_COMPARE_RESULTS",
            "data": result,
            "timestamp": int(time.time() * 1000),
        }
        await websocket.send(json.dumps(message))
        logger.info(f"📤 Sent Video Compare results: {result.get('success', False)}")

    async def send_status_update(self, websocket, action, data):
        """Send status update to extension"""
        message = {"action": action, "data": data, "timestamp": int(time.time() * 1000)}
        await websocket.send(json.dumps(message))
        logger.info(f"📤 Sent status update: {action}")

    async def send_response(self, websocket, action, data):
        """Send response to extension"""
        message = {"action": action, "data": data, "timestamp": int(time.time() * 1000)}
        await websocket.send(json.dumps(message))
        logger.info(f"📤 Sent response: {action}")

    async def send_error(self, websocket, error_message, cradle_id=None, action_context="DESKTOP_ERROR"):
        """Send error message to extension"""
        message = {
            "action": "ERROR",
            "error": error_message,
            "timestamp": int(time.time() * 1000),
        }
        if cradle_id:
            message["cradle_id"] = cradle_id
            
        await websocket.send(json.dumps(message))
        logger.error(f"📤 Sent error: {error_message}")
        
        # Log to Backend
        asyncio.create_task(self.api_client.log_system_event(
            component="desktop_app",
            action=action_context,
            message=error_message,
            is_error=True,
            cradle_id=cradle_id
        ))

    async def broadcast_message(self, message):
        """Broadcast message to all connected clients"""
        if self.clients:
            logger.info(
                f"📡 Broadcasting to {len(self.clients)} clients: {message.get('action', 'unknown')}"
            )
            await asyncio.gather(
                *[client.send(json.dumps(message)) for client in self.clients],
                return_exceptions=True,
            )

    async def start_server(self, host="0.0.0.0", port=8765):
        """Start the WebSocket server"""
        logger.info(f"Starting WebSocket server on {host}:{port}")

        async def handler(websocket, path):
            await self.handle_client(websocket, path)

        start_server = websockets.serve(handler, host, port)
        logger.info("WebSocket server is running...")

        await start_server

        # Keep server running
        await asyncio.Future()  # Run forever


# Server instance
server = WebSocketServer()


async def main():
    """Main server function"""
    try:
        await server.start_server()
    except KeyboardInterrupt:
        logger.info("Server shutting down...")
    except Exception as e:
        logger.error(f"Server error: {str(e)}")


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Run server
    asyncio.run(main())
