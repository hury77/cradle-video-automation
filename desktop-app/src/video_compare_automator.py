import asyncio
import logging
import os
import platform
import time
import subprocess
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

logger = logging.getLogger(__name__)


class VideoCompareAutomator:
    def __init__(self):
        self.driver = None
        self.wait_timeout = 30

    def check_chrome_debugging(self):
        """Check if Chrome remote debugging is available on port 9222"""
        try:
            import requests

            response = requests.get("http://localhost:9222/json/version", timeout=3)
            if response.status_code == 200:
                logger.info("✅ Chrome remote debugging already available on port 9222")
                return True
            else:
                logger.info("❌ Chrome debugging port responds but not ready")
                return False
        except Exception as e:
            logger.info(f"❌ Chrome remote debugging not available: {e}")
            return False

    def start_chrome_debugging(self):
        """Start Chrome with remote debugging while preserving existing session"""
        try:
            system = platform.system()

            if system == "Darwin":  # macOS
                # Zachowaj istniejący profil Chrome
                user_data_dir = os.path.expanduser(
                    "~/Library/Application Support/Google/Chrome"
                )

                cmd = [
                    "open",
                    "-na",
                    "Google Chrome",
                    "--args",
                    "--remote-debugging-port=9222",
                    f"--user-data-dir={user_data_dir}",
                ]

                logger.info(
                    "🚀 Starting Chrome with remote debugging (preserving session)..."
                )
                subprocess.run(cmd, check=False)

            elif system == "Windows":
                # Windows path
                user_data_dir = os.path.expanduser(
                    "~/AppData/Local/Google/Chrome/User Data"
                )
                chrome_path = (
                    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
                )

                cmd = [
                    chrome_path,
                    "--remote-debugging-port=9222",
                    f"--user-data-dir={user_data_dir}",
                ]

                logger.info("🚀 Starting Chrome with remote debugging on Windows...")
                subprocess.Popen(cmd)

            else:  # Linux
                user_data_dir = os.path.expanduser("~/.config/google-chrome")

                cmd = [
                    "google-chrome",
                    "--remote-debugging-port=9222",
                    f"--user-data-dir={user_data_dir}",
                ]

                logger.info("🚀 Starting Chrome with remote debugging on Linux...")
                subprocess.Popen(cmd)

            # Poczekaj na uruchomienie
            logger.info("⏳ Waiting for Chrome debugging to start...")
            for i in range(10):  # Max 10 sekund
                time.sleep(1)
                if self.check_chrome_debugging():
                    logger.info(f"✅ Chrome debugging ready after {i+1} seconds")
                    return True

            logger.error("❌ Chrome debugging did not start within 10 seconds")
            return False

        except Exception as e:
            logger.error(f"❌ Failed to start Chrome debugging: {e}")
            return False

    def setup_browser(self):
        """Setup browser - connect to existing Chrome session with debugging"""
        try:
            # ✅ SPRAWDŹ CZY CHROME DEBUGGING JUŻ DZIAŁA
            if not self.check_chrome_debugging():
                logger.info("🔧 Chrome debugging not available - starting...")
                if not self.start_chrome_debugging():
                    raise Exception("Failed to start Chrome with remote debugging")

            # ✅ POŁĄCZ SIĘ DO ISTNIEJĄCEJ SESJI CHROME
            chrome_options = Options()
            chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")

            # Dodatkowe opcje dla stabilności
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")

            logger.info("🔗 Connecting to existing Chrome session on port 9222...")

            # NIE POTRZEBUJEMY SERVICE - ŁĄCZYMY SIĘ DO ISTNIEJĄCEJ SESJI
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.implicitly_wait(10)

            logger.info("✅ Connected to existing Chrome session successfully")
            logger.info(f"🌐 Current page: {self.driver.current_url}")

            return True

        except Exception as e:
            logger.error(f"❌ Failed to connect to Chrome session: {e}")
            logger.error("💡 Make sure Chrome is running and accessible")

            # Fallback do standardowego Chrome (nowe okno)
            logger.info("🔄 Attempting fallback to new Chrome instance...")
            return self.setup_browser_fallback()

    def setup_browser_fallback(self):
        """Fallback: Setup new Chrome instance (original method)"""
        try:
            chrome_options = Options()
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")

            # Detect platform and architecture
            system = platform.system()
            machine = platform.machine()

            logger.info(f"Detected platform: {system}, architecture: {machine}")

            service = None

            if system == "Darwin":  # macOS
                # ✅ SPRAWDŹ HOMEBREW CHROMEDRIVER NAJPIERW
                homebrew_paths = [
                    "/opt/homebrew/bin/chromedriver",
                    "/usr/local/bin/chromedriver",
                ]

                for homebrew_path in homebrew_paths:
                    if os.path.exists(homebrew_path) and os.access(
                        homebrew_path, os.X_OK
                    ):
                        logger.info(f"Using Homebrew ChromeDriver: {homebrew_path}")
                        service = Service(homebrew_path)
                        break

                if not service:
                    try:
                        # Get ChromeDriver path from webdriver-manager
                        driver_path = ChromeDriverManager().install()
                        logger.info(f"WebDriver Manager returned: {driver_path}")

                        # ✅ POPRAWKA: Znajdź prawdziwy chromedriver w folderze
                        driver_dir = os.path.dirname(driver_path)

                        # Najpierw sprawdź bezpośrednio chromedriver
                        actual_chromedriver = os.path.join(driver_dir, "chromedriver")

                        if os.path.exists(actual_chromedriver) and os.access(
                            actual_chromedriver, os.X_OK
                        ):
                            logger.info(
                                f"Found actual ChromeDriver at: {actual_chromedriver}"
                            )
                            service = Service(actual_chromedriver)
                        else:
                            # Szukaj we wszystkich plikach w folderze
                            logger.info(f"Searching for chromedriver in: {driver_dir}")
                            logger.info(f"Directory contents: {os.listdir(driver_dir)}")

                            for file in os.listdir(driver_dir):
                                file_path = os.path.join(driver_dir, file)
                                if (
                                    file == "chromedriver"
                                    or file.startswith("chromedriver")
                                ) and os.access(file_path, os.X_OK):
                                    logger.info(
                                        f"Found executable ChromeDriver: {file_path}"
                                    )
                                    service = Service(file_path)
                                    break

                            if not service:
                                # Sprawdź podkatalogi
                                for root, dirs, files in os.walk(driver_dir):
                                    for file in files:
                                        if file == "chromedriver" and os.access(
                                            os.path.join(root, file), os.X_OK
                                        ):
                                            chromedriver_path = os.path.join(root, file)
                                            logger.info(
                                                f"Found ChromeDriver in subdirectory: {chromedriver_path}"
                                            )
                                            service = Service(chromedriver_path)
                                            break
                                    if service:
                                        break

                        if not service:
                            raise Exception(
                                "Executable chromedriver not found in webdriver-manager cache"
                            )

                    except Exception as e:
                        logger.warning(f"webdriver-manager failed: {e}")

                        # Fallback do manualnych ścieżek
                        if machine in ["arm64", "M1", "M2"]:
                            # Apple Silicon
                            possible_paths = [
                                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                                "./chromedriver_mac_arm64",
                                os.path.expanduser("~/chromedriver"),
                            ]
                        else:
                            # Intel Mac
                            possible_paths = [
                                "./chromedriver_mac_intel",
                                os.path.expanduser("~/chromedriver"),
                            ]

                        for path in possible_paths:
                            if os.path.exists(path) and os.access(path, os.X_OK):
                                logger.info(f"Using ChromeDriver from: {path}")
                                service = Service(path)
                                break

                        if not service:
                            logger.error(
                                "ChromeDriver not found. Installing via Homebrew..."
                            )
                            logger.error("Run: brew install --cask chromedriver")
                            logger.error(
                                "Or download manually from: https://chromedriver.chromium.org/"
                            )
                            raise Exception(
                                "ChromeDriver not found - please install manually"
                            )

            elif system == "Windows":
                try:
                    driver_path = ChromeDriverManager().install()
                    service = Service(driver_path)
                except Exception as e:
                    logger.error(f"Failed to setup ChromeDriver on Windows: {e}")
                    raise

            else:  # Linux
                try:
                    driver_path = ChromeDriverManager().install()
                    service = Service(driver_path)
                except Exception as e:
                    logger.error(f"Failed to setup ChromeDriver on Linux: {e}")
                    raise

            # Create the driver
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.implicitly_wait(10)

            logger.info("Chrome browser setup successful (fallback mode)")
            return True

        except Exception as e:
            logger.error(f"Failed to setup browser in fallback mode: {e}")
            if self.driver:
                self.driver.quit()
                self.driver = None
            return False

    async def upload_videos(self, acceptance_file, emission_file, cradle_id):
        """Upload acceptance and emission videos to Video Compare"""
        try:
            logger.info(f"Starting video upload for CradleID: {cradle_id}")
            logger.info(f"Acceptance file: {acceptance_file}")
            logger.info(f"Emission file: {emission_file}")

            # Verify files exist
            if not os.path.exists(acceptance_file):
                raise Exception(f"Acceptance file not found: {acceptance_file}")
            if not os.path.exists(emission_file):
                raise Exception(f"Emission file not found: {emission_file}")

            # ✅ FRESH SETUP - ZAWSZE NOWY CONNECTION
            logger.info("🔄 Setting up fresh browser connection...")
            if self.driver:
                try:
                    logger.info("🗑️ Closing existing driver...")
                    self.driver.quit()
                except Exception as e:
                    logger.warning(f"Error closing existing driver: {e}")
                self.driver = None

            if not self.setup_browser():
                raise Exception("Failed to setup browser")

            # Navigate to Video Compare page
            video_compare_url = "https://cradle.egplusww.pl/vcompare/add/"
            logger.info(f"Navigating to: {video_compare_url}")
            self.driver.get(video_compare_url)

            # Wait for page to load
            await asyncio.sleep(3)

            # Wait for and fill acceptance file input
            logger.info("Looking for acceptance file input...")
            acceptance_selectors = [
                "input[type='file'][name*='acceptance']",
                "input[type='file'][id*='acceptance']",
                "input[type='file'][name*='video1']",
                "input[type='file'][id*='video1']",
                "input[type='file']:first-of-type",
            ]

            acceptance_input = None
            for selector in acceptance_selectors:
                try:
                    acceptance_input = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    logger.info(f"Found acceptance input with selector: {selector}")
                    break
                except TimeoutException:
                    continue

            if not acceptance_input:
                logger.error("Could not find acceptance file input")
                raise Exception("Acceptance file input not found")

            logger.info("Uploading acceptance file...")
            acceptance_input.send_keys(acceptance_file)
            await asyncio.sleep(2)

            # Wait for and fill emission file input
            logger.info("Looking for emission file input...")
            emission_selectors = [
                "input[type='file'][name*='emission']",
                "input[type='file'][id*='emission']",
                "input[type='file'][name*='video2']",
                "input[type='file'][id*='video2']",
                "input[type='file']:last-of-type",
                "input[type='file']:nth-of-type(2)",
            ]

            emission_input = None
            for selector in emission_selectors:
                try:
                    emission_input = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    # Sprawdź czy to nie ten sam input co acceptance
                    if emission_input != acceptance_input:
                        logger.info(f"Found emission input with selector: {selector}")
                        break
                except TimeoutException:
                    continue

            if not emission_input:
                logger.error("Could not find emission file input")
                raise Exception("Emission file input not found")

            logger.info("Uploading emission file...")
            emission_input.send_keys(emission_file)
            await asyncio.sleep(2)

            # Look for submit button
            logger.info("Looking for submit button...")
            submit_selectors = [
                "button[type='submit']",
                "input[type='submit']",
                "button:contains('Submit')",
                "button:contains('Compare')",
                "button:contains('Upload')",
                "button:contains('Start')",
                ".btn-primary",
                ".submit-btn",
                "button.btn",
                "[value='Submit']",
            ]

            submit_button = None
            for selector in submit_selectors:
                try:
                    submit_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if submit_button.is_enabled() and submit_button.is_displayed():
                        logger.info(f"Found submit button with selector: {selector}")
                        break
                except:
                    continue

            if not submit_button:
                # Try to find any button that might be the submit
                buttons = self.driver.find_elements(By.TAG_NAME, "button")
                for button in buttons:
                    button_text = button.text.lower()
                    if (
                        any(
                            word in button_text
                            for word in ["submit", "compare", "upload", "start"]
                        )
                        and button.is_enabled()
                    ):
                        submit_button = button
                        logger.info(f"Found submit button by text: {button.text}")
                        break

            if submit_button:
                logger.info("Clicking submit button...")
                submit_button.click()
                await asyncio.sleep(3)

                # Check if we're redirected to results page
                current_url = self.driver.current_url
                logger.info(f"After submit, current URL: {current_url}")

                if (
                    "result" in current_url
                    or "compare" in current_url
                    or "processing" in current_url
                ):
                    logger.info("Video comparison submitted successfully!")
                    return {
                        "success": True,
                        "message": "Videos uploaded and comparison started",
                        "result_url": current_url,
                    }
                else:
                    logger.info("Videos uploaded, checking for success indicators...")

                    # Check for success messages or processing indicators
                    success_indicators = [
                        "success",
                        "uploaded",
                        "processing",
                        "comparing",
                        "started",
                    ]

                    page_text = self.driver.page_source.lower()
                    if any(indicator in page_text for indicator in success_indicators):
                        return {
                            "success": True,
                            "message": "Videos uploaded successfully",
                            "result_url": current_url,
                        }
                    else:
                        return {
                            "success": True,
                            "message": "Videos uploaded (status unclear)",
                            "result_url": current_url,
                        }

            else:
                logger.warning("Submit button not found, but files were uploaded")
                return {
                    "success": False,
                    "message": "Files uploaded, but could not find submit button",
                    "result_url": self.driver.current_url,
                }

        except TimeoutException as e:
            logger.error(f"Timeout during video upload: {e}")
            return {"success": False, "error": f"Timeout: {str(e)}"}

        except Exception as e:
            logger.error(f"Error during video upload: {e}")
            return {"success": False, "error": str(e)}

    def close_browser(self):
        """Close the browser and cleanup"""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("Browser closed successfully")
            except Exception as e:
                logger.error(f"Error closing browser: {e}")
            finally:
                self.driver = None

    def __del__(self):
        """Cleanup when object is destroyed"""
        self.close_browser()


# Test function
async def test_video_compare():
    """Test function for Video Compare automation"""
    automator = VideoCompareAutomator()

    try:
        # Test with dummy files (replace with actual file paths)
        acceptance_file = "/path/to/acceptance.mp4"
        emission_file = "/path/to/emission.mp4"
        cradle_id = "123456"

        result = await automator.upload_videos(
            acceptance_file, emission_file, cradle_id
        )
        logger.info(f"Upload result: {result}")

    finally:
        automator.close_browser()


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Run test
    asyncio.run(test_video_compare())