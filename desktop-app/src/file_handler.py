import os
import requests
import logging
from pathlib import Path
import asyncio
import glob
import shutil

class FileHandler:
    def __init__(self, download_base_path=None):
        self.logger = logging.getLogger(__name__)
        
        # Default Downloads folder
        if download_base_path is None:
            home = Path.home()
            self.download_base_path = home / "Downloads"
        else:
            self.download_base_path = Path(download_base_path)
            
        self.logger.info(f"FileHandler initialized with base path: {self.download_base_path}")

    async def handle_files_detected(self, websocket, data):
        """Handle FILES_DETECTED message from extension"""
        try:
            cradle_id = data.get('cradleId')
            acceptance_file = data.get('acceptanceFile')
            emission_file = data.get('emissionFile')
            
            self.logger.info(f"📁 Processing files for CradleID: {cradle_id}")
            
            if not cradle_id:
                await self.send_error(websocket, "No CradleID provided")
                return
                
            # Create cradle folder
            cradle_folder = self.download_base_path / cradle_id
            cradle_folder.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"📂 Created/verified folder: {cradle_folder}")
            
            results = {
                'cradle_id': cradle_id,
                'folder': str(cradle_folder),
                'files_downloaded': [],
                'errors': []
            }
            
            # Download acceptance file
            if acceptance_file:
                result = await self.download_file(acceptance_file, cradle_folder, "acceptance")
                if result['success']:
                    results['files_downloaded'].append(result)
                else:
                    results['errors'].append(result)
                    
            # Download emission file  
            if emission_file:
                result = await self.download_file(emission_file, cradle_folder, "emission")
                if result['success']:
                    results['files_downloaded'].append(result)
                else:
                    results['errors'].append(result)
            
            # Send results back to extension
            await self.send_download_results(websocket, results)
            
        except Exception as e:
            self.logger.error(f"❌ Error handling files: {str(e)}")
            await self.send_error(websocket, f"File handling error: {str(e)}")

    async def download_file(self, file_info, folder_path, file_type):
        """Download single file - handles both attachments and network paths"""
        try:
            # Check if it's a network path (emission file)
            if file_info.get('type') == 'network_path' and file_info.get('path'):
                self.logger.info(f"🌐 Detected network path for {file_type}")
                cradle_id = folder_path.name  # Get CradleID from folder name
                return await self.handle_network_emission_file(file_info, folder_path, cradle_id)
            
            # 🔥 NOWE: Handle emission attachments with suffix
            if file_type == "emission" and file_info.get('type') == 'attachment':
                return await self.handle_emission_attachment(file_info, folder_path)
            
            # Regular file download (acceptance attachments)
            url = file_info.get('url')
            original_name = file_info.get('name', f"{file_type}_{file_info.get('row', 'unknown')}.mp4")
            
            if not url:
                return {
                    'success': False,
                    'type': file_type,
                    'error': 'No URL provided'
                }
            
            self.logger.info(f"⬇️ Downloading {file_type}: {original_name}")
            self.logger.info(f"   URL: {url}")
            
            # Download file with headers for better compatibility
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Accept': '*/*',
                'Referer': 'https://cradle.egplusww.pl/',
            }
            
            response = requests.get(url, stream=True, timeout=30, headers=headers)
            response.raise_for_status()
            
            # Save to folder
            file_path = folder_path / original_name
            
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            file_size = file_path.stat().st_size
            self.logger.info(f"✅ Downloaded {file_type}: {original_name} ({file_size:,} bytes)")
            
            return {
                'success': True,
                'type': file_type,
                'filename': original_name,
                'path': str(file_path),
                'size': file_size,
                'url': url
            }
            
        except requests.RequestException as e:
            self.logger.error(f"❌ Download failed for {file_type}: {str(e)}")
            return {
                'success': False,
                'type': file_type,
                'error': str(e),
                'url': url if 'url' in locals() else 'unknown'
            }
            
        except Exception as e:
            self.logger.error(f"❌ Unexpected error downloading {file_type}: {str(e)}")
            return {
                'success': False,
                'type': file_type,
                'error': str(e),
                'url': url if 'url' in locals() else 'unknown'
            }

    async def handle_emission_attachment(self, file_info, folder_path):
        """Handle emission attachment downloads with _emis suffix"""
        try:
            url = file_info.get('url')
            original_name = file_info.get('name', f"emission_{file_info.get('row', 'unknown')}.mp4")
            
            if not url:
                return {'success': False, 'type': 'emission_attachment', 'error': 'No URL provided'}
            
            # Check if acceptance file with same name exists
            acceptance_files = list(folder_path.glob(f"*{original_name}*"))
            final_name = original_name
            
            if acceptance_files:
                # Add _emis suffix: file.mp4 → file_emis.mp4
                name_parts = original_name.rsplit('.', 1)
                if len(name_parts) == 2:
                    final_name = f"{name_parts[0]}_emis.{name_parts[1]}"
                else:
                    final_name = f"{original_name}_emis"
                
                self.logger.info(f"📝 Adding suffix to avoid conflict: {original_name} → {final_name}")
            
            # Download with proper headers (for cookies)
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Accept': '*/*',
                'Referer': 'https://cradle.egplusww.pl/',
            }
            
            self.logger.info(f"⬇️ Downloading emission attachment: {final_name}")
            self.logger.info(f"   URL: {url}")
            
            response = requests.get(url, stream=True, timeout=30, headers=headers)
            response.raise_for_status()
            
            # Save with final name
            file_path = folder_path / final_name
            
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            file_size = file_path.stat().st_size
            self.logger.info(f"✅ Downloaded emission attachment: {final_name} ({file_size:,} bytes)")
            
            return {
                'success': True,
                'type': 'emission_attachment',
                'filename': final_name,
                'original_name': original_name,
                'path': str(file_path),
                'size': file_size,
                'url': url
            }
            
        except Exception as e:
            self.logger.error(f"❌ Emission attachment download failed: {str(e)}")
            return {'success': False, 'type': 'emission_attachment', 'error': str(e)}

    async def handle_network_emission_file(self, file_info, cradle_folder, cradle_id):
        """Handle emission files from network drives"""
        try:
            network_path = file_info.get('path')
            if not network_path:
                return {'success': False, 'error': 'No network path provided'}
                
            self.logger.info(f"🌐 Processing network path: {network_path}")
            
            # Clean and normalize path
            if network_path.startswith('/Volumes/'):
                # macOS network path
                search_path = network_path
            elif network_path.startswith('\\\\'):
                # Windows UNC path
                search_path = network_path.replace('\\', '/')
            else:
                search_path = network_path
                
            # Remove trailing slashes
            search_path = search_path.rstrip('/')
            
            self.logger.info(f"🔍 Searching in: {search_path}")
            
            # Common video extensions
            extensions = ['mp4', 'mov', 'avi', 'mkv', 'mxf', 'prores', 'MOV', 'MP4']
            
            found_files = []
            
            # ✅ ROZSZERZONE WZORCE WYSZUKIWANIA - TO JEST GŁÓWNA ZMIANA!
            search_patterns = [
                # Bezpośrednio w folderze
                f"{search_path}/{cradle_id}*",           # 879712*
                f"{search_path}/_{cradle_id}*",          # _879712* ← NOWY!
                f"{search_path}/*{cradle_id}*",          # *879712* ← NOWY!
                f"{search_path}/{cradle_id}_*",          # 879712_* ← NOWY!
                f"{search_path}/_{cradle_id}_*",         # _879712_* ← NOWY!
                
                # W podfolderach
                f"{search_path}/*/{cradle_id}*",         # */879712*
                f"{search_path}/*/_{cradle_id}*",        # */_879712* ← NOWY!
                f"{search_path}/*/*{cradle_id}*",        # */*879712* ← NOWY!
                f"{search_path}/*/{cradle_id}_*",        # */879712_* ← NOWY!
                f"{search_path}/*/_{cradle_id}_*",       # */_879712_* ← NOWY!
                
                # Deep search (wszystkie poziomy)
                f"{search_path}/**/{cradle_id}*",        # **/879712*
                f"{search_path}/**/_{cradle_id}*",       # **/_879712* ← NOWY!
                f"{search_path}/**/*{cradle_id}*",       # **/*879712* ← NOWY!
                f"{search_path}/**/{cradle_id}_*",       # **/879712_* ← NOWY!
                f"{search_path}/**/_{cradle_id}_*",      # **/_879712_* ← NOWY!
            ]
            
            for pattern_base in search_patterns:
                for ext in extensions:
                    pattern = f"{pattern_base}.{ext}"
                    self.logger.info(f"🔍 Searching pattern: {pattern}")
                    
                    try:
                        matches = glob.glob(pattern, recursive=True)
                        if matches:
                            found_files.extend(matches)
                            self.logger.info(f"✅ Found {len(matches)} files with pattern: {pattern}")
                            # Log first few matches
                            for match in matches[:3]:
                                self.logger.info(f"   📄 {os.path.basename(match)}")
                            # ✅ Jeśli znalazł pliki, przerwij dalsze szukanie
                            break
                    except Exception as e:
                        self.logger.warning(f"⚠️ Pattern search failed: {pattern} - {str(e)}")
                
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
                self.logger.info(f"✅ Network file copied: {filename} ({file_size:,} bytes)")
                
                return {
                    'success': True,
                    'type': 'emission_network',
                    'filename': filename,
                    'path': str(destination),
                    'source': source_file,
                    'size': file_size,
                    'found_files_count': len(found_files),
                    'all_found_files': [os.path.basename(f) for f in found_files[:5]]  # First 5 filenames
                }
            else:
                error_msg = f'No files found starting with {cradle_id} in {search_path}'
                self.logger.warning(f"❌ {error_msg}")
                
                # ✅ LEPSZE DEBUGOWANIE - List what's actually in the directory
                try:
                    if os.path.exists(search_path):
                        files_in_dir = [f for f in os.listdir(search_path) if not f.startswith('.')][:10]
                        self.logger.info(f"📂 Files in directory (first 10): {files_in_dir}")
                        
                        # ✅ SPRAWDŹ CZY JEST JAKIŚ PLIK Z PODOBNYM ID
                        similar_files = [f for f in files_in_dir if cradle_id in f]
                        if similar_files:
                            self.logger.info(f"🔍 Files containing '{cradle_id}': {similar_files}")
                        
                    else:
                        self.logger.warning(f"📂 Directory does not exist: {search_path}")
                except Exception as e:
                    self.logger.warning(f"📂 Cannot list directory: {str(e)}")
                    
                return {
                    'success': False,
                    'error': error_msg,
                    'search_path': search_path,
                    'patterns_tried': len(search_patterns) * len(extensions)
                }
                
        except Exception as e:
            self.logger.error(f"❌ Network file error: {str(e)}")
            return {'success': False, 'error': str(e)}

    async def send_download_results(self, websocket, results):
        """Send download results back to extension"""
        import json
        
        message = {
            'action': 'DOWNLOAD_RESULTS',
            'data': results,
            'timestamp': int(asyncio.get_event_loop().time() * 1000)
        }
        
        await websocket.send(json.dumps(message))
        self.logger.info(f"📤 Sent download results: {len(results['files_downloaded'])} files, {len(results['errors'])} errors")

    async def send_error(self, websocket, error_message):
        """Send error message to extension"""
        import json
        
        message = {
            'action': 'DOWNLOAD_ERROR', 
            'error': error_message,
            'timestamp': int(asyncio.get_event_loop().time() * 1000)
        }
        
        await websocket.send(json.dumps(message))
        self.logger.error(f"📤 Sent error: {error_message}")