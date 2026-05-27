from PIL import Image
import numpy as np

img_path = "/Users/hubert.rycaj/.gemini/antigravity-ide/brain/4bcb4b93-98b6-4ae4-a7af-1d34456e0f54/extracted_frame.png"

try:
    img = Image.open(img_path)
    img_data = np.array(img)
    
    # Check if there are any pixels that are not black (black is [0,0,0] or close to it)
    # Let's count non-black pixels (luminance > 10)
    # Convert to grayscale first for simplicity
    gray = img.convert('L')
    gray_data = np.array(gray)
    
    total_pixels = gray_data.size
    black_pixels = np.sum(gray_data <= 10)
    non_black_pixels = total_pixels - black_pixels
    
    print("--- IMAGE PIXEL ANALYSIS ---")
    print(f"Total pixels: {total_pixels}")
    print(f"Black pixels (val <= 10): {black_pixels} ({black_pixels / total_pixels * 100:.2f}%)")
    print(f"Non-black pixels (val > 10): {non_black_pixels} ({non_black_pixels / total_pixels * 100:.2f}%)")
    
    # Print average pixel value
    avg_val = np.mean(gray_data)
    print(f"Average brightness: {avg_val:.2f}")
    
    if non_black_pixels > 100:
        print("🎉 The image has COLOR/CONTENT (it is NOT entirely black)!")
    else:
        print("💀 The image is ENTIRELY BLACK!")
        
except Exception as e:
    print(f"Error analyzing image: {e}")
