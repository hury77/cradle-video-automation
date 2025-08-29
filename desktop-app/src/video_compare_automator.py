import os
import asyncio
import logging
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time

logger = logging.getLogger(__name__)

class VideoCompareAutomator:
    def __init__(self):
        self.driver = None
        self.wait = None
        self.video_compare_url = "https://cradle.egplusww.pl/vcompare/add/"
        
    async def setup_browser(self):
        """Initialize Chrome WebDriver"""
        try:
            logger.info("🌐 Setting up Chrome WebDriver...")
            
            # Chrome options
            chrome_options = Options()
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            # chrome_options.add_argument("--headless")  # Uncomment for headless
            
            # Setup ChromeDriver
            service = Service(ChromeDriverManager().install())
            
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.wait = WebDriverWait(self.driver, 30)
            
            logger.info("✅ Chrome WebDriver initialized")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to setup browser: {str(e)}")
            return False
    
    async def upload_and_compare(self, cradle_id, acceptance_file_path, emission_file_path):
        """Main method to upload files and start comparison"""
        try:
            logger.info(f"🎬 Starting Video Compare for CradleID: {cradle_id}")
            logger.info(f"📁 Acceptance file: {acceptance_file_path}")
            logger.info(f"📁 Emission file: {emission_file_path}")
            
            # Verify files exist
            if not os.path.exists(acceptance_file_path):
                raise Exception(f"Acceptance file not found: {acceptance_file_path}")
            if not os.path.exists(emission_file_path):
                raise Exception(f"Emission file not found: {emission_file_path}")
            
            # Setup browser if not already done
            if not self.driver:
                setup_success = await self.setup_browser()
                if not setup_success:
                    raise Exception("Failed to setup browser")
            
            # Navigate to Video Compare
            logger.info("🌐 Navigating to Video Compare...")
            self.driver.get(self.video_compare_url)
            
            # Wait for page load
            await asyncio.sleep(3)
            
            # Upload Video A (acceptance file - left side)
            logger.info("📤 Uploading Video A (acceptance file)...")
            await self.upload_video_a(acceptance_file_path)
            
            # Upload Video B (emission file - right side) 
            logger.info("📤 Uploading Video B (emission file)...")
            await self.upload_video_b(emission_file_path)
            
            # Submit comparison
            logger.info("🚀 Submitting comparison...")
            await self.submit_comparison()
            
            # Monitor progress
            logger.info("⏳ Monitoring comparison progress...")
            comparison_url = await self.monitor_progress()
            
            return {
                'success': True,
                'cradle_id': cradle_id,
                'comparison_url': comparison_url,
                'message': 'Video comparison started successfully'
            }
            
        except Exception as e:
            logger.error(f"❌ Video Compare automation failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'cradle_id': cradle_id
            }
    
    async def upload_video_a(self, file_path):
        """Upload acceptance file to Video A (left side)"""
        try:
            # Find Video A upload area (left side)
            # Looking for file input or dropzone for Video A
            video_a_inputs = self.driver.find_elements(By.CSS_SELECTOR, 
                "input[type='file']")
            
            if len(video_a_inputs) >= 1:
                # First file input is usually Video A
                video_a_input = video_a_inputs[0]
                video_a_input.send_keys(file_path)
                logger.info("✅ Video A uploaded successfully")
                await asyncio.sleep(2)
            else:
                raise Exception("Video A upload input not found")
                
        except Exception as e:
            logger.error(f"❌ Failed to upload Video A: {str(e)}")
            raise
    
    async def upload_video_b(self, file_path):
        """Upload emission file to Video B (right side)"""
        try:
            # Find Video B upload area (right side)
            video_b_inputs = self.driver.find_elements(By.CSS_SELECTOR, 
                "input[type='file']")
            
            if len(video_b_inputs) >= 2:
                # Second file input is usually Video B
                video_b_input = video_b_inputs[1]
                video_b_input.send_keys(file_path)
                logger.info("✅ Video B uploaded successfully")
                await asyncio.sleep(2)
            else:
                raise Exception("Video B upload input not found")
                
        except Exception as e:
            logger.error(f"❌ Failed to upload Video B: {str(e)}")
            raise
    
    async def submit_comparison(self):
        """Click Submit all files button"""
        try:
            # Look for submit button
            submit_selectors = [
                "input[value*='Submit all files']",
                "button:contains('Submit all files')",
                "*[type='submit']",
                ".submit-btn",
                "#submit-btn"
            ]
            
            submit_button = None
            for selector in submit_selectors:
                try:
                    submit_button = self.wait.until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    break
                except:
                    continue
            
            if submit_button:
                submit_button.click()
                logger.info("✅ Comparison submitted successfully")
                await asyncio.sleep(3)
            else:
                raise Exception("Submit button not found")
                
        except Exception as e:
            logger.error(f"❌ Failed to submit comparison: {str(e)}")
            raise
    
    async def monitor_progress(self):
        """Monitor comparison progress and return results URL"""
        try:
            # Wait for redirect to results page or progress page
            await asyncio.sleep(5)
            
            current_url = self.driver.current_url
            logger.info(f"🔍 Current URL after submit: {current_url}")
            
            # Check if we're on a progress or results page
            if "vcompare" in current_url and current_url != self.video_compare_url:
                logger.info("✅ Redirected to comparison page")
                return current_url
            else:
                logger.warning("⚠️ No redirect detected, staying on current page")
                return current_url
                
        except Exception as e:
            logger.error(f"❌ Error monitoring progress: {str(e)}")
            return self.driver.current_url if self.driver else None
    
    async def close_browser(self):
        """Close the browser"""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("🔒 Browser closed")
            except Exception as e:
                logger.error(f"❌ Error closing browser: {str(e)}")
            finally:
                self.driver = None
                self.wait = None
    
    def __del__(self):
        """Cleanup on object destruction"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass