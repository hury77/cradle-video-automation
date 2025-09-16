import asyncio
import logging
import os
import json
import requests
import websockets
import time

logger = logging.getLogger(__name__)


class VideoCompareAutomator:
    def __init__(self):
        self.devtools_port = 9223
        self.devtools_url = f"http://localhost:{self.devtools_port}"
        self.upload_timeout = 300  # 5 minutes
        self.result_wait_timeout = 600  # 10 minutes
        self._message_id = 1  # ✅ FIX #1: Instance variable for message ID tracking

    def _get_next_message_id(self):
        """Get next message ID and increment counter"""
        current_id = self._message_id
        self._message_id += 1
        return current_id

    def check_chrome_debugging(self):
        """Check if Chrome has remote debugging enabled on port 9223"""
        try:
            response = requests.get(f"{self.devtools_url}/json", timeout=5)
            if response.status_code == 200:
                tabs = response.json()
                logger.info(f"✅ Chrome debugging ACTIVE on port 9223")
                logger.info(f"📊 Found {len(tabs)} open tabs")

                # Check for Video Compare tab
                vc_tab = None
                for tab in tabs:
                    title = tab.get("title", "No title")
                    url = tab.get("url", "No URL")

                    if "vcompare/add" in url:
                        vc_tab = tab
                        logger.info(f"🎬 FOUND Video Compare tab: {title}")

                return True, vc_tab
            else:
                logger.error(
                    f"❌ Chrome debugging port responds with code {response.status_code}"
                )
                return False, None

        except requests.exceptions.ConnectionError:
            logger.error("❌ Chrome debugging NOT ACTIVE - port 9223 closed")
            logger.error("💡 Start Chrome with: --remote-debugging-port=9223")
            return False, None
        except Exception as e:
            logger.error(f"❌ Error checking Chrome debugging: {e}")
            return False, None

    def find_video_compare_tab(self):
        """Find Video Compare tab"""
        try:
            response = requests.get(f"{self.devtools_url}/json", timeout=5)
            tabs = response.json()

            for tab in tabs:
                url = tab.get("url", "")
                if "vcompare/add" in url:
                    logger.info(f"✅ Found VC tab: {tab['title']} - {url}")
                    return tab

            logger.error("❌ Video Compare tab not found")
            return None
        except Exception as e:
            logger.error(f"❌ Error finding VC tab: {e}")
            return None

    async def upload_videos_via_devtools(
        self, acceptance_file, emission_file, cradle_id
    ):
        """Complete CDP implementation - actually uploads files"""
        try:
            logger.info(f"🎬 Starting CDP file upload for CradleID: {cradle_id}")

            # Reset message ID counter for this session
            self._message_id = 1

            # 1. Check Chrome debugging
            debugging_ok, vc_tab = self.check_chrome_debugging()
            if not debugging_ok:
                return {
                    "success": False,
                    "error": "Chrome debugging not available",
                    "solution": "Start Chrome with --remote-debugging-port=9223",
                    "ai_action": "retry_after_chrome_restart",
                }

            # 2. Find Video Compare tab
            if not vc_tab:
                vc_tab = self.find_video_compare_tab()
                if not vc_tab:
                    return {
                        "success": False,
                        "error": "Video Compare tab not found",
                        "solution": "Open https://cradle.egplusww.pl/vcompare/add/ in Chrome",
                        "ai_action": "open_video_compare_tab",
                    }

            # 3. Verify files exist
            if not os.path.exists(acceptance_file):
                return {
                    "success": False,
                    "error": f"Acceptance file not found: {acceptance_file}",
                    "ai_action": "check_file_downloads",
                }
            if not os.path.exists(emission_file):
                return {
                    "success": False,
                    "error": f"Emission file not found: {emission_file}",
                    "ai_action": "check_file_downloads",
                }

            logger.info(f"📁 Files verified:")
            logger.info(
                f"   Acceptance: {os.path.basename(acceptance_file)} ({os.path.getsize(acceptance_file):,} bytes)"
            )
            logger.info(
                f"   Emission: {os.path.basename(emission_file)} ({os.path.getsize(emission_file):,} bytes)"
            )

            # 4. Connect to tab via WebSocket
            ws_url = vc_tab["webSocketDebuggerUrl"]
            logger.info(f"🔗 Connecting to tab WebSocket: {ws_url}")

            async with websockets.connect(ws_url) as websocket:

                # ✅ FIX #4: Enable domains with proper sequencing
                logger.info("🔧 Enabling CDP domains...")
                await self._send_cdp_command(
                    websocket, self._get_next_message_id(), "Runtime.enable"
                )
                await self._send_cdp_command(
                    websocket, self._get_next_message_id(), "Page.enable"
                )
                await self._send_cdp_command(
                    websocket, self._get_next_message_id(), "DOM.enable"
                )

                # ✅ FIX #4: Wait for DOM to be ready
                logger.info("⏳ Waiting for DOM readiness...")
                await asyncio.sleep(2)

                # 5. Find file input elements with unique identification
                logger.info("🔍 Finding and marking file input elements...")
                js_find_inputs = """
                (function() {
                    const inputs = document.querySelectorAll('input[type="file"]');
                    const result = [];
                    
                    inputs.forEach((input, index) => {
                        // ✅ FIX #3: Add unique CDP identifier
                        const uniqueId = 'cdp-file-input-' + index + '-' + Date.now();
                        input.setAttribute('data-cdp-id', uniqueId);
                        
                        result.push({
                            index: index,
                            cdp_id: uniqueId,
                            id: input.id || '',
                            name: input.name || '',
                            accept: input.accept || '',
                            className: input.className || ''
                        });
                    });
                    
                    return {
                        success: true,
                        inputs: result,
                        count: inputs.length
                    };
                })();
                """

                response = await self._send_cdp_command(
                    websocket,
                    self._get_next_message_id(),
                    "Runtime.evaluate",
                    {"expression": js_find_inputs, "returnByValue": True},
                )

                if not response or "result" not in response:
                    return {
                        "success": False,
                        "error": "Failed to find file inputs",
                        "ai_action": "check_page_loaded",
                    }

                inputs_info = response["result"]["result"]["value"]
                if not inputs_info.get("success"):
                    return {
                        "success": False,
                        "error": "No file inputs found on page",
                        "ai_action": "verify_video_compare_page",
                    }

                inputs = inputs_info.get("inputs", [])
                if len(inputs) < 2:
                    return {
                        "success": False,
                        "error": f"Need 2 file inputs, found {len(inputs)}",
                        "available_inputs": inputs,
                        "ai_action": "check_video_compare_form",
                    }

                logger.info(f"✅ Found {len(inputs)} file inputs")
                for i, inp in enumerate(inputs):
                    logger.info(
                        f"   Input {i}: id='{inp.get('id')}' name='{inp.get('name')}' accept='{inp.get('accept')}'"
                    )

                # 6. Identify which input is for acceptance and which for emission
                acceptance_input_idx = 0  # Default: first input
                emission_input_idx = 1  # Default: second input

                # ✅ IMPROVED: Smarter identification
                for i, inp in enumerate(inputs):
                    inp_id = inp.get("id", "").lower()
                    inp_name = inp.get("name", "").lower()
                    inp_class = inp.get("className", "").lower()

                    # Look for acceptance indicators
                    if any(
                        keyword in inp_id + inp_name + inp_class
                        for keyword in ["acceptance", "accept", "qa", "proof"]
                    ):
                        acceptance_input_idx = i
                        logger.info(
                            f"🎯 Identified acceptance input by keyword: Input {i}"
                        )
                    # Look for emission indicators
                    elif any(
                        keyword in inp_id + inp_name + inp_class
                        for keyword in ["emission", "broadcast", "final", "master"]
                    ):
                        emission_input_idx = i
                        logger.info(
                            f"🎯 Identified emission input by keyword: Input {i}"
                        )

                logger.info(f"📋 Final input assignment:")
                logger.info(
                    f"   Acceptance → Input {acceptance_input_idx} (cdp_id: {inputs[acceptance_input_idx].get('cdp_id')})"
                )
                logger.info(
                    f"   Emission → Input {emission_input_idx} (cdp_id: {inputs[emission_input_idx].get('cdp_id')})"
                )

                # 7. Upload acceptance file
                logger.info("📤 Uploading acceptance file...")
                acceptance_cdp_id = inputs[acceptance_input_idx].get("cdp_id")
                upload_result = await self._upload_file_to_input(
                    websocket, acceptance_cdp_id, acceptance_file
                )
                if not upload_result.get("success"):
                    return {
                        "success": False,
                        "error": f"Failed to upload acceptance file: {upload_result.get('error')}",
                        "ai_action": "retry_file_upload",
                    }

                # 8. Upload emission file
                logger.info("📤 Uploading emission file...")
                emission_cdp_id = inputs[emission_input_idx].get("cdp_id")
                upload_result = await self._upload_file_to_input(
                    websocket, emission_cdp_id, emission_file
                )
                if not upload_result.get("success"):
                    return {
                        "success": False,
                        "error": f"Failed to upload emission file: {upload_result.get('error')}",
                        "ai_action": "retry_file_upload",
                    }

                # 9. Wait for files to be processed
                logger.info("⏳ Waiting for files to be processed...")
                await asyncio.sleep(3)

                # 10. Find and click submit button
                logger.info("🔍 Finding submit button...")
                js_find_submit = """
                (function() {
                    const buttons = document.querySelectorAll('button, input[type="submit"], [role="button"], .btn, .button');
                    
                    for (let btn of buttons) {
                        const text = (btn.textContent || btn.value || btn.innerText || '').toLowerCase().trim();
                        const ariaLabel = (btn.getAttribute('aria-label') || '').toLowerCase();
                        const title = (btn.getAttribute('title') || '').toLowerCase();
                        const className = (btn.className || '').toLowerCase();
                        
                        // ✅ FIX #5: Broader submit button detection
                        const submitKeywords = [
                            'submit', 'compare', 'upload', 'send', 'start', 'proceed', 
                            'analyze', 'process', 'run', 'execute', 'begin', 'go',
                            'next', 'continue', 'confirm'
                        ];
                        
                        const allText = text + ' ' + ariaLabel + ' ' + title + ' ' + className;
                        
                        if (submitKeywords.some(keyword => allText.includes(keyword)) || 
                            btn.type === 'submit' || 
                            btn.form) {
                            
                            // Mark button for clicking
                            btn.setAttribute('data-cdp-submit', 'true');
                            return {
                                success: true,
                                text: text || 'unlabeled button',
                                type: btn.type || 'button',
                                className: btn.className || '',
                                found: true
                            };
                        }
                    }
                    
                    return {
                        success: false, 
                        error: 'Submit button not found',
                        buttonCount: buttons.length
                    };
                })();
                """

                response = await self._send_cdp_command(
                    websocket,
                    self._get_next_message_id(),
                    "Runtime.evaluate",
                    {"expression": js_find_submit, "returnByValue": True},
                )

                if response and "result" in response:
                    submit_info = response["result"]["result"]["value"]
                    if submit_info.get("success"):
                        logger.info(
                            f"✅ Found submit button: '{submit_info.get('text')}'"
                        )

                        # Click submit button
                        js_click_submit = """
                        (function() {
                            const btn = document.querySelector('[data-cdp-submit="true"]');
                            if (btn) {
                                btn.click();
                                return {success: true, clicked: btn.textContent || btn.value || 'button'};
                            }
                            return {success: false, error: 'Submit button lost'};
                        })();
                        """

                        logger.info("🖱️ Clicking submit button...")
                        click_response = await self._send_cdp_command(
                            websocket,
                            self._get_next_message_id(),
                            "Runtime.evaluate",
                            {"expression": js_click_submit, "returnByValue": True},
                        )

                        if click_response and "result" in click_response:
                            click_result = click_response["result"]["result"]["value"]
                            if click_result.get("success"):
                                logger.info(
                                    f"✅ Submit button clicked: {click_result.get('clicked')}"
                                )

                                # 11. Wait for comparison results
                                logger.info("⏳ Waiting for comparison results...")
                                comparison_result = await self._wait_for_results(
                                    websocket
                                )

                                return {
                                    "success": True,
                                    "message": "Video comparison completed successfully",
                                    "cradle_id": cradle_id,
                                    "files_uploaded": {
                                        "acceptance": os.path.basename(acceptance_file),
                                        "emission": os.path.basename(emission_file),
                                    },
                                    "comparison_result": comparison_result,
                                    "ai_action": "process_results",
                                }
                            else:
                                return {
                                    "success": False,
                                    "error": f"Failed to click submit: {click_result.get('error')}",
                                    "ai_action": "manual_submit_check",
                                }
                        else:
                            return {
                                "success": False,
                                "error": "No response from submit click",
                                "ai_action": "manual_submit_check",
                            }
                    else:
                        return {
                            "success": False,
                            "error": f"Submit button not found. Available buttons: {submit_info.get('buttonCount', 0)}",
                            "ai_action": "inspect_page_buttons",
                        }
                else:
                    return {
                        "success": False,
                        "error": "Failed to search for submit button",
                        "ai_action": "check_page_state",
                    }

        except websockets.exceptions.ConnectionClosed:
            return {
                "success": False,
                "error": "WebSocket connection closed during upload",
                "ai_action": "retry_connection",
            }
        except Exception as e:
            logger.error(f"❌ CDP upload error: {e}")
            return {"success": False, "error": str(e), "ai_action": "debug_error"}

    async def _send_cdp_command(self, websocket, message_id, method, params=None):
        """Send CDP command and wait for response"""
        command = {"id": message_id, "method": method}
        if params:
            command["params"] = params

        try:
            await websocket.send(json.dumps(command))

            # Wait for response with timeout
            timeout = 30  # 30 seconds
            start_time = time.time()

            while time.time() - start_time < timeout:
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5)
                    data = json.loads(response)

                    if data.get("id") == message_id:
                        if "error" in data:
                            logger.error(f"CDP command error: {data['error']}")
                            return None
                        return data
                    # Ignore other messages (events, etc.)
                except asyncio.TimeoutError:
                    continue

            logger.error(f"CDP command timeout: {method}")
            return None

        except Exception as e:
            logger.error(f"CDP command failed: {method} - {e}")
            return None

    async def _upload_file_to_input(self, websocket, cdp_id, file_path):
        """Upload file to specific input using Page.setFileInputFiles"""
        try:
            logger.info(f"📁 Uploading {os.path.basename(file_path)} to input {cdp_id}")

            # Get document node
            doc_response = await self._send_cdp_command(
                websocket, self._get_next_message_id(), "DOM.getDocument"
            )
            if not doc_response:
                return {"success": False, "error": "Could not get document"}

            # Find the marked input element using CSS selector
            search_response = await self._send_cdp_command(
                websocket,
                self._get_next_message_id(),
                "DOM.querySelector",
                {
                    "nodeId": doc_response["result"]["root"]["nodeId"],
                    "selector": f"input[data-cdp-id='{cdp_id}']",
                },
            )

            if not search_response or not search_response.get("result", {}).get(
                "nodeId"
            ):
                return {
                    "success": False,
                    "error": f"Could not find input with cdp_id: {cdp_id}",
                }

            node_id = search_response["result"]["nodeId"]
            logger.info(f"✅ Found input element, node ID: {node_id}")

            # Upload file using Page.setFileInputFiles
            upload_response = await self._send_cdp_command(
                websocket,
                self._get_next_message_id(),
                "Page.setFileInputFiles",
                {"files": [file_path], "nodeId": node_id},
            )

            if upload_response:
                logger.info(
                    f"✅ File uploaded successfully: {os.path.basename(file_path)}"
                )
                return {"success": True, "file": os.path.basename(file_path)}
            else:
                return {"success": False, "error": "Page.setFileInputFiles failed"}

        except Exception as e:
            logger.error(f"❌ File upload error: {e}")
            return {"success": False, "error": str(e)}

    async def _wait_for_results(self, websocket):
        """Wait for comparison results with intelligent monitoring"""
        try:
            logger.info("⏳ Monitoring page for comparison results...")

            start_time = time.time()
            last_status = ""

            while time.time() - start_time < self.result_wait_timeout:
                # ✅ Enhanced result detection
                js_check_results = """
                (function() {
                    const bodyText = document.body.textContent || document.body.innerText || '';
                    const bodyHTML = document.body.innerHTML || '';
                    
                    // Look for success indicators
                    const successIndicators = [
                        'comparison complete', 'results ready', 'analysis complete', 
                        'processing complete', 'finished', 'done', 'success'
                    ];
                    
                    // Look for error indicators
                    const errorIndicators = [
                        'error', 'failed', 'unable to process', 'invalid file',
                        'upload failed', 'comparison failed', 'timeout'
                    ];
                    
                    // Look for processing indicators
                    const processingIndicators = [
                        'processing', 'analyzing', 'comparing', 'uploading',
                        'please wait', 'in progress', 'working'
                    ];
                    
                    const lowerBodyText = bodyText.toLowerCase();
                    
                    let status = 'unknown';
                    let message = 'Monitoring comparison...';
                    let details = '';
                    
                    // Check for completion
                    if (successIndicators.some(indicator => lowerBodyText.includes(indicator))) {
                        status = 'complete';
                        message = 'Comparison completed successfully';
                        // Try to extract result details
                        const resultDiv = document.querySelector('.result, .comparison-result, [class*="result"]');
                        if (resultDiv) {
                            details = resultDiv.textContent || resultDiv.innerText || '';
                        }
                    }
                    // Check for errors
                    else if (errorIndicators.some(indicator => lowerBodyText.includes(indicator))) {
                        status = 'error';
                        message = 'Comparison failed';
                        // Try to extract error details
                        const errorDiv = document.querySelector('.error, .alert-danger, [class*="error"]');
                        if (errorDiv) {
                            details = errorDiv.textContent || errorDiv.innerText || '';
                        }
                    }
                    // Check if still processing
                    else if (processingIndicators.some(indicator => lowerBodyText.includes(indicator))) {
                        status = 'processing';
                        message = 'Still processing comparison...';
                        
                        // Look for progress indicators
                        const progressDiv = document.querySelector('[class*="progress"], .progress-bar');
                        if (progressDiv) {
                            details = progressDiv.textContent || progressDiv.innerText || '';
                        }
                    }
                    
                    return {
                        status: status,
                        message: message,
                        details: details.substring(0, 500), // Limit details length
                        timestamp: Date.now(),
                        bodyLength: bodyText.length
                    };
                })();
                """

                response = await self._send_cdp_command(
                    websocket,
                    self._get_next_message_id(),
                    "Runtime.evaluate",
                    {"expression": js_check_results, "returnByValue": True},
                )

                if response and "result" in response:
                    result_info = response["result"]["result"]["value"]
                    status = result_info.get("status", "unknown")
                    message = result_info.get("message", "")
                    details = result_info.get("details", "")

                    # Only log if status changed
                    if status != last_status:
                        logger.info(f"🔄 Status change: {message}")
                        if details:
                            logger.info(f"   Details: {details[:200]}...")
                        last_status = status

                    if status == "complete":
                        logger.info("✅ Comparison completed successfully!")
                        return {
                            "status": "complete",
                            "message": message,
                            "details": details,
                            "duration": int(time.time() - start_time),
                        }
                    elif status == "error":
                        logger.error("❌ Comparison failed!")
                        return {
                            "status": "error",
                            "message": message,
                            "details": details,
                            "duration": int(time.time() - start_time),
                        }
                    # Continue monitoring if still processing

                # Wait before next check (shorter intervals at start, longer later)
                elapsed = time.time() - start_time
                if elapsed < 60:  # First minute: check every 5 seconds
                    await asyncio.sleep(5)
                elif elapsed < 300:  # Next 4 minutes: check every 15 seconds
                    await asyncio.sleep(15)
                else:  # After 5 minutes: check every 30 seconds
                    await asyncio.sleep(30)

            # Timeout reached
            logger.warning("⚠️ Results wait timeout reached")
            return {
                "status": "timeout",
                "message": "Comparison results wait timeout",
                "duration": int(time.time() - start_time),
            }

        except Exception as e:
            logger.error(f"❌ Error waiting for results: {e}")
            return {
                "status": "error",
                "message": str(e),
                "duration": (
                    int(time.time() - start_time) if "start_time" in locals() else 0
                ),
            }

    # Backward compatibility methods
    async def upload_videos(self, acceptance_file, emission_file, cradle_id):
        """Main entry point - calls CDP implementation"""
        return await self.upload_videos_via_devtools(
            acceptance_file, emission_file, cradle_id
        )

    async def handle_hybrid_upload(self, data):
        """Handle upload request from extension"""
        try:
            acceptance_file = data.get("acceptance_file")
            emission_file = data.get("emission_file")
            cradle_id = data.get("cradle_id", "unknown")

            if not acceptance_file or not emission_file:
                return {
                    "success": False,
                    "error": "Missing file paths",
                    "ai_action": "check_file_detection",
                }

            return await self.upload_videos_via_devtools(
                acceptance_file, emission_file, cradle_id
            )

        except Exception as e:
            logger.error(f"❌ Hybrid upload error: {e}")
            return {
                "success": False,
                "error": str(e),
                "ai_action": "debug_hybrid_upload",
            }


# Test function
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    async def test():
        automator = VideoCompareAutomator()
        result = automator.check_chrome_debugging()
        print(f"Test result: {result}")

    asyncio.run(test())
