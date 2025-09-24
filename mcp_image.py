#!/usr/bin/env python3

import os
import sys
import asyncio
import httpx
import logging
import re
import time
import json
from datetime import datetime, timedelta
from urllib.parse import urlparse, quote, unquote
from mcp.server.fastmcp import FastMCP, Context
from typing import List, Dict, Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import WebDriverException, NoSuchElementException, TimeoutException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    logger = logging.getLogger("image-mcp")
    logger.warning("Selenium not available. Google Images search will use alternative method.")

# List of blocked royalty-free domains
ROYALTY_FREE_DOMAINS = [
    "pexels.com", "unsplash.com", "pixabay.com", "freepik.com", "stock.adobe.com"
]

def is_royalty_free_url(url: str) -> bool:
    parsed = urlparse(url)
    return any(domain in parsed.netloc for domain in ROYALTY_FREE_DOMAINS)

# Azure Blob Storage imports
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions

TEMP_DIR = "./Temp"
DATA_DIR = "./data"

# Azure Blob Storage configuration (same as test.py)
AZURE_CONNECTION_STRING = os.getenv('AZURE_CONNECTION_STRING')
CONTAINER_NAME = "image-mcp"

# Ensure directories exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

# Configure logging
log_filename = os.path.join(DATA_DIR, datetime.now().strftime("%d-%m-%y.log"))
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

file_handler = logging.FileHandler(log_filename)
file_handler.setFormatter(formatter)
console_handler = logging.StreamHandler(sys.stderr)
console_handler.setFormatter(formatter)

logger = logging.getLogger("image-mcp")
logger.setLevel(logging.DEBUG)
logger.addHandler(file_handler)
logger.addHandler(console_handler)
logger.propagate = False

# Create a FastMCP server instance
mcp = FastMCP("image-service")

class GoogleImageSearcher:
    """
    Google Images searcher that extracts direct image URLs.
    Uses Selenium when available, falls back to simpler HTTP method.
    """
    
    def __init__(self, headless=True):
        self.headless = headless
        self.driver = None
        
    def _setup_driver(self):
        """Setup Chrome WebDriver with appropriate options."""
        if not SELENIUM_AVAILABLE:
            return False
            
        try:
            options = Options()
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-extensions')
            options.add_argument('--disable-plugins')
            options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            if self.headless:
                options.add_argument('--headless')
                
            # Try to use system chromedriver first
            try:
                self.driver = webdriver.Chrome(options=options)
            except WebDriverException:
                logger.warning("System chromedriver not found")
                return False
                
            self.driver.set_window_size(1920, 1080)
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup Chrome driver: {str(e)}")
            return False
    
    async def _search_simple_method(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Simple Google Images search using HTTP requests.
        This method extracts image URLs from the HTML without executing JavaScript.
        """
        try:
            # Encode the search query for URL
            encoded_query = quote(query)
            # Try both old and new Google Images URL formats
            search_urls = [
                f"https://www.google.com/search?q={encoded_query}&udm=2&hl=en",  # New format
                f"https://www.google.com/search?q={encoded_query}&tbm=isch&hl=en",  # Old format
            ]
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            
            html_content = None
            successful_url = None
            
            async with httpx.AsyncClient(headers=headers, timeout=30.0, follow_redirects=True) as client:
                for search_url in search_urls:
                    try:
                        response = await client.get(search_url)
                        response.raise_for_status()
                        html_content = response.text
                        successful_url = search_url
                        break
                    except Exception as e:
                        logger.debug(f"Failed with URL {search_url}: {str(e)}")
                        continue
                
                if not html_content:
                    return [{"error": "Failed to fetch Google Images page with any URL format", "status": "failed"}]
                
                logger.info(f"Successfully fetched page using: {successful_url}")
                
                # Extract image URLs using regex patterns
                image_results = []
                
                # Enhanced patterns to find image URLs in the HTML
                patterns = [
                    r'"ou":"([^"]*)"',  # Original URL pattern
                    r'"data-src":"([^"]*)"',  # Data source pattern
                    r'"src":"([^"]*)"',  # Source pattern
                    r'https?://[^"\s,]+\.(?:jpg|jpeg|png|gif|webp)(?:[^"\s,]*)?',  # Direct image URLs
                    r'https?://[^"\s,]*(?:jpg|jpeg|png|gif|webp)[^"\s,]*',  # Image URLs with extensions
                ]
                
                found_urls = set()
                for pattern in patterns:
                    matches = re.findall(pattern, html_content, re.IGNORECASE)
                    for match in matches:
                        # Clean and validate the URL
                        url = match.replace('\\u003d', '=').replace('\\u0026', '&').replace('\\/', '/')
                        
                        # Decode URL if needed
                        try:
                            url = unquote(url)
                        except:
                            pass
                            
                        if url.startswith('http') and any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                            # Skip certain unwanted domains and patterns
                            skip_patterns = [
                                'gstatic.com', 'ggpht.com', 'googleusercontent.com', 'encrypted-tbn',
                                'logo', 'icon', 'avatar', 'profile', 'thumbnail'
                            ]
                            if not any(skip in url.lower() for skip in skip_patterns):
                                # Only include URLs that look like actual images
                                if len(url) > 20 and len(url) < 2000:  # Reasonable URL length
                                    found_urls.add(url)
                
                # Convert to list and limit results
                unique_urls = list(found_urls)[:max_results * 3]  # Get more URLs to filter better ones
                
                # Try to validate URLs and get metadata
                valid_results = []
                async with httpx.AsyncClient(timeout=10.0) as test_client:
                    for i, url in enumerate(unique_urls):
                        if len(valid_results) >= max_results:
                            break
                            
                        try:
                            # Quick head request to validate the URL
                            head_response = await test_client.head(url)
                            if head_response.status_code == 200:
                                content_type = head_response.headers.get('content-type', '')
                                if content_type.startswith('image/'):
                                    # Try to get some metadata by parsing the URL
                                    parsed = urlparse(url)
                                    domain = parsed.netloc
                                    
                                    # Extract filename for title
                                    filename = os.path.basename(parsed.path)
                                    if filename:
                                        title = filename
                                    else:
                                        title = f"Image from {domain}"
                                    
                                    valid_results.append({
                                        "url": url,
                                        "title": title,
                                        "source": f"https://{domain}",
                                        "status": "success"
                                    })
                                    
                        except Exception as e:
                            logger.debug(f"Error validating URL {url}: {str(e)}")
                            # If validation fails, still include the URL but mark it as unvalidated
                            if len(valid_results) < max_results:
                                parsed = urlparse(url)
                                domain = parsed.netloc
                                
                                valid_results.append({
                                    "url": url,
                                    "title": f"Image from {domain} (unvalidated)",
                                    "source": f"https://{domain}",
                                    "status": "success"
                                })
                
                logger.info(f"Found {len(valid_results)} images using simple method for query: {query}")
                return valid_results
                
        except Exception as e:
            logger.error(f"Simple method search failed: {str(e)}")
            return [{"error": f"Simple search method failed: {str(e)}", "status": "failed"}]
    
    def search_images_selenium(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Search for images using Selenium WebDriver (requires Chrome and chromedriver).
        """
        try:
            if not self._setup_driver():
                return [{"error": "Failed to setup Chrome driver. Please ensure Chrome and chromedriver are installed.", "status": "failed"}]
            
            # Encode the search query for URL
            encoded_query = quote(query)
            search_url = f"https://www.google.com/search?q={encoded_query}&tbm=isch&hl=en"
            
            logger.info(f"Searching Google Images for: {query}")
            self.driver.get(search_url)
            
            # Wait for page to load
            time.sleep(3)
            
            # Handle cookie consent if present
            try:
                consent_button = WebDriverWait(self.driver, 3).until(
                    EC.element_to_be_clickable((By.ID, "L2AGLb"))
                )
                consent_button.click()
                time.sleep(1)
            except TimeoutException:
                pass  # No consent dialog appeared
            
            image_results = []
            count = 0
            page_height = 0
            
            while count < max_results:
                # Find all image elements on current page
                try:
                    # Try multiple selectors for image elements
                    img_elements = self.driver.find_elements(By.CSS_SELECTOR, "img[data-src]")
                    if not img_elements:
                        img_elements = self.driver.find_elements(By.CSS_SELECTOR, "img[src*='gstatic']")
                    if not img_elements:
                        img_elements = self.driver.find_elements(By.CSS_SELECTOR, "div[data-tbnid] img")
                    
                    if not img_elements:
                        logger.warning("No image elements found, trying alternative approach")
                        break
                    
                    for img in img_elements[count:]:
                        if count >= max_results:
                            break
                            
                        try:
                            # Click on the image to get full resolution
                            self.driver.execute_script("arguments[0].click();", img)
                            time.sleep(2)
                            
                            # Get the large image from the preview panel
                            large_img_selectors = [
                                "img.n3VNCb",  # Common class for large images
                                "img.iPVvYb", 
                                "img[src*='http']:not([src*='gstatic']):not([src*='encrypted'])",
                                "div[data-tbnid] img[src*='http']"
                            ]
                            
                            large_img = None
                            for selector in large_img_selectors:
                                try:
                                    large_img = self.driver.find_element(By.CSS_SELECTOR, selector)
                                    if large_img:
                                        break
                                except NoSuchElementException:
                                    continue
                            
                            if large_img:
                                img_url = large_img.get_attribute("src")
                                if img_url and img_url.startswith("http") and "encrypted" not in img_url and "gstatic" not in img_url:
                                    # Get additional metadata
                                    title = img.get_attribute("alt") or f"Image {count + 1}"
                                    
                                    # Try to get source website
                                    source = "Unknown"
                                    try:
                                        source_elem = self.driver.find_element(By.CSS_SELECTOR, "div.fxgdke a")
                                        source = source_elem.get_attribute("href") or "Unknown"
                                    except NoSuchElementException:
                                        pass
                                    
                                    image_results.append({
                                        "url": img_url,
                                        "title": title,
                                        "source": source,
                                        "status": "success"
                                    })
                                    
                                    count += 1
                                    logger.info(f"Found image {count}: {img_url}")
                            
                        except Exception as e:
                            logger.debug(f"Error processing individual image: {str(e)}")
                            continue
                    
                    # Scroll down to load more images if needed
                    if count < max_results:
                        current_height = self.driver.execute_script("return document.body.scrollHeight")
                        if current_height > page_height:
                            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                            page_height = current_height
                            time.sleep(2)
                        else:
                            # Try clicking "Show more results" button
                            try:
                                show_more = self.driver.find_element(By.CSS_SELECTOR, "input[value*='Show more']")
                                show_more.click()
                                time.sleep(3)
                            except NoSuchElementException:
                                break  # No more images to load
                    
                except Exception as e:
                    logger.error(f"Error during image search: {str(e)}")
                    break
            
            logger.info(f"Found {len(image_results)} images for query: {query}")
            return image_results
            
        except Exception as e:
            error_msg = f"Selenium Google Images search failed: {str(e)}"
            logger.error(error_msg)
            return [{"error": error_msg, "status": "failed"}]
            
        finally:
            if self.driver:
                try:
                    self.driver.quit()
                except Exception:
                    pass
                self.driver = None
    
    async def search_images(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Search for images, trying Selenium first and falling back to simple method.
        """
        if SELENIUM_AVAILABLE:
            # Try Selenium method first
            try:
                results = self.search_images_selenium(query, max_results)
                if results and any(r.get("status") == "success" for r in results):
                    return results
                else:
                    logger.info("Selenium method didn't return results, trying simple method")
            except Exception as e:
                logger.warning(f"Selenium method failed: {str(e)}, trying simple method")
        
        # Fall back to simple method
        return await self._search_simple_method(query, max_results)

def upload_to_azure_blob(local_file_path: str = None, file_data: bytes = None, blob_name: str = None) -> Dict[str, Any]:
    """
    Upload a file to Azure Blob Storage and return a SAS URL.
    Can accept either a file path or raw bytes data.
    
    :param local_file_path: Path to the local file to upload
    :param file_data: Raw bytes data to upload (alternative to local_file_path)
    :param blob_name: Name of the blob in Azure
    :return: Dictionary with upload result
    """
    try:
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
        container_client = blob_service_client.get_container_client(CONTAINER_NAME)

        # Ensure container exists
        try:
            container_client.create_container()
        except Exception:
            pass  # Container already exists

        # Get data to upload
        if file_data is not None:
            data_to_upload = file_data
        elif local_file_path is not None:
            with open(local_file_path, "rb") as f:
                data_to_upload = f.read()
        else:
            raise ValueError("Either local_file_path or file_data must be provided")

        # Upload
        container_client.upload_blob(name=blob_name, data=data_to_upload, overwrite=True)
        
        # Generate a SAS URL that expires in 24 hours
        account_name = blob_service_client.account_name
        account_key = AZURE_CONNECTION_STRING.split("AccountKey=")[1].split(";")[0]
        
        sas_token = generate_blob_sas(
            account_name=account_name,
            container_name=CONTAINER_NAME,
            blob_name=blob_name,
            account_key=account_key,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.utcnow() + timedelta(hours=24)
        )
        
        blob_url = f"https://{account_name}.blob.core.windows.net/{CONTAINER_NAME}/{blob_name}?{sas_token}"
        
        logger.info(f"Successfully uploaded {blob_name} to Azure Blob Storage")
        
        return {
            "status": "success",
            "filename": blob_name,
            "blob_url": blob_url,
            "markdown": f"![{blob_name}]({blob_url})",
            "size_bytes": len(data_to_upload)
        }
        
    except Exception as e:
        error_msg = f"Failed to upload to Azure Blob Storage: {str(e)}"
        logger.error(error_msg)
        return {"status": "failed", "error": error_msg}

def download_from_azure_blob(filename: str, download_path: str) -> Dict[str, Any]:
    """Download a file from Azure Blob Storage."""
    try:
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
        blob_client = blob_service_client.get_blob_client(container=CONTAINER_NAME, blob=filename)
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(download_path), exist_ok=True)
        
        with open(download_path, "wb") as download_file:
            download_file.write(blob_client.download_blob().readall())
        
        logger.info(f"Successfully downloaded {filename} to {download_path}")
        
        return {
            "status": "success",
            "filename": filename,
            "download_path": download_path
        }
        
    except Exception as e:
        error_msg = f"Failed to download from Azure Blob Storage: {str(e)}"
        logger.error(error_msg)
        return {"status": "failed", "error": error_msg}

@mcp.tool()
async def search_google_images(
    search_query: str,
    max_results: int = 10,
    ctx: Context = None
) -> List[Dict[str, Any]]:
    """
    Search Google Images for the given query and return direct image URLs.
    
    This tool searches Google Images and returns direct URLs to images that can be 
    immediately displayed by clicking them. The LLM can then choose the best image(s)
    and use other tools to download and upload them to Azure Blob Storage.
    
    Args:
        search_query: The search term to look for images (e.g., "red sunset over ocean")
        max_results: Maximum number of image URLs to return (default: 10, max: 20)
        
    Returns:
        A list of dictionaries containing image information:
        - {"url": str, "title": str, "source": str, "status": "success"} for successful results
        - {"error": str, "status": "failed"} for failed searches
    """
    try:
        if not search_query.strip():
            return [{"error": "Search query cannot be empty", "status": "failed"}]
        
        # Limit max_results to prevent excessive scraping
        max_results = min(max_results, 20)
        
        logger.info(f"Starting Google Images search for: '{search_query}'")
        
        # Create searcher instance
        searcher = GoogleImageSearcher(headless=True)
        
        # Perform the search (now async)
        results = await searcher.search_images(search_query, max_results)
        
        if not results:
            return [{"error": "No images found for the search query", "status": "failed"}]
        
        # Log summary
        successful_results = [r for r in results if r.get("status") == "success"]
        logger.info(f"Google Images search completed: {len(successful_results)} images found for '{search_query}'")
        
        return results
        
    except Exception as e:
        error_msg = f"Google Images search failed: {str(e)}"
        logger.error(error_msg)
        return [{"error": error_msg, "status": "failed"}]

@mcp.tool()
async def save_images_to_azure(
    image_sources: List[str],
    blob_prefix: str = "image",
    ctx: Context = None
) -> List[Dict[str, Any]]:
    """
    Fetch images from URLs or local paths and upload them directly to Azure Blob Storage.
    Returns markdown-ready links for each successfully uploaded image.
    
    This is the main tool for LLMs to save images and get markdown links.
    
    Args:
        image_sources: A list of image URLs or local file paths
        blob_prefix: Prefix for blob names (default: "image")
        
    Returns:
        A list of dictionaries containing upload results:
        - {"source": str, "blob_url": str, "markdown": str, "filename": str, "status": "success"}
        - {"source": str, "error": str, "status": "failed"}
    """
    try:
        if not image_sources:
            return [{"error": "No image sources provided", "status": "failed"}]
        
        results = []
        
        for i, source in enumerate(image_sources):
            try:
                # Block royalty-free image sources
                if source.startswith(("http://", "https://")) and is_royalty_free_url(source):
                    results.append({
                        "source": source,
                        "error": "Royalty-free image sources are not allowed.",
                        "status": "failed"
                    })
                    continue

                # Generate unique blob name
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                extension = "png"  # Default extension

                # Try to get extension from source
                if source.startswith(("http://", "https://")):
                    parsed = urlparse(source)
                    if '.' in parsed.path:
                        extension = parsed.path.split('.')[-1].lower()
                        if extension not in ['png', 'jpg', 'jpeg', 'gif', 'webp']:
                            extension = "png"
                elif os.path.exists(source):
                    _, ext = os.path.splitext(source)
                    if ext:
                        extension = ext[1:].lower()

                blob_name = f"{blob_prefix}_{i+1:03d}_{timestamp}.{extension}"

                # Fetch and upload the image
                if source.startswith(("http://", "https://")):
                    # Handle URL
                    async with httpx.AsyncClient() as client:
                        response = await client.get(source)
                        response.raise_for_status()

                        # Verify it's an image
                        content_type = response.headers.get('content-type', '')
                        if not content_type.startswith('image/'):
                            results.append({
                                "source": source,
                                "error": f"Not an image (got {content_type})",
                                "status": "failed"
                            })
                            continue

                        # Upload to Azure
                        upload_result = upload_to_azure_blob(
                            file_data=response.content,
                            blob_name=blob_name
                        )

                elif os.path.exists(source):
                    # Handle local file
                    upload_result = upload_to_azure_blob(
                        local_file_path=source,
                        blob_name=blob_name
                    )
                else:
                    results.append({
                        "source": source,
                        "error": "File not found and not a valid URL",
                        "status": "failed"
                    })
                    continue

                # Process upload result
                if upload_result["status"] == "success":
                    results.append({
                        "source": source,
                        "blob_url": upload_result["blob_url"],
                        "markdown": upload_result["markdown"],
                        "filename": upload_result["filename"],
                        "size_bytes": upload_result["size_bytes"],
                        "status": "success"
                    })
                    logger.info(f"Successfully uploaded {source} to Azure as {blob_name}")
                else:
                    results.append({
                        "source": source,
                        "error": upload_result["error"],
                        "status": "failed"
                    })

            except Exception as e:
                error_msg = f"Error processing {source}: {str(e)}"
                logger.error(error_msg)
                results.append({
                    "source": source,
                    "error": error_msg,
                    "status": "failed"
                })
        
        # Log summary
        success_count = sum(1 for r in results if r["status"] == "success")
        logger.info(f"Processed {len(image_sources)} images: {success_count} successful, {len(results) - success_count} failed")
        
        return results
        
    except Exception as e:
        error_msg = f"Failed to process images: {str(e)}"
        logger.error(error_msg)
        return [{"source": src, "error": error_msg, "status": "failed"} for src in image_sources]

@mcp.tool()
async def upload_single_image_to_azure(
    image_source: str,
    blob_name: str = None,
    ctx: Context = None
) -> Dict[str, Any]:
    """
    Upload a single image to Azure Blob Storage and return a markdown-ready link.
    
    This is the primary tool for LLMs to upload individual images and get markdown links.
    
    Args:
        image_source: Image URL or local file path to upload
        blob_name: Custom name for the blob (optional, auto-generated if not provided)
        
    Returns:
        Dictionary with upload result:
        - {"source": str, "blob_url": str, "markdown": str, "filename": str, "status": "success"}
        - {"source": str, "error": str, "status": "failed"}
    """
    try:
        # Block royalty-free image sources
        if image_source.startswith(("http://", "https://")) and is_royalty_free_url(image_source):
            return {
                "source": image_source,
                "error": "Royalty-free image sources are not allowed.",
                "status": "failed"
            }

        # Auto-generate blob name if not provided
        if blob_name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            if image_source.startswith(("http://", "https://")):
                # Extract filename from URL
                parsed = urlparse(image_source)
                filename = os.path.basename(parsed.path) or "image"
                name_part = os.path.splitext(filename)[0]
                extension = "png"
                if '.' in filename:
                    extension = filename.split('.')[-1].lower()
                    if extension not in ['png', 'jpg', 'jpeg', 'gif', 'webp']:
                        extension = "png"
                blob_name = f"{name_part}_{timestamp}.{extension}"
            else:
                # Use local filename
                filename = os.path.basename(image_source)
                name_part = os.path.splitext(filename)[0] or "image"
                extension = os.path.splitext(filename)[1][1:].lower() or "png"
                blob_name = f"{name_part}_{timestamp}.{extension}"

        # Upload the image
        if image_source.startswith(("http://", "https://")):
            async with httpx.AsyncClient() as client:
                response = await client.get(image_source)
                response.raise_for_status()

                # Verify it's an image
                content_type = response.headers.get('content-type', '')
                if not content_type.startswith('image/'):
                    return {
                        "source": image_source,
                        "error": f"Not an image (got {content_type})",
                        "status": "failed"
                    }

                upload_result = upload_to_azure_blob(file_data=response.content, blob_name=blob_name)
        else:
            if not os.path.exists(image_source):
                return {
                    "source": image_source,
                    "error": "File not found",
                    "status": "failed"
                }

            upload_result = upload_to_azure_blob(local_file_path=image_source, blob_name=blob_name)

        if upload_result["status"] == "success":
            return {
                "source": image_source,
                "blob_url": upload_result["blob_url"],
                "markdown": upload_result["markdown"],
                "filename": upload_result["filename"],
                "size_bytes": upload_result["size_bytes"],
                "status": "success"
            }
        else:
            return {
                "source": image_source,
                "error": upload_result["error"],
                "status": "failed"
            }

    except Exception as e:
        error_msg = f"Failed to upload image: {str(e)}"
        logger.error(f"Error uploading {image_source}: {error_msg}")
        return {
            "source": image_source,
            "error": error_msg,
            "status": "failed"
        }

@mcp.tool()
async def download_image_from_azure(
    filename: str,
    download_path: str,
    ctx: Context = None
) -> Dict[str, str]:
    """
    Download an image from Azure Blob Storage to a local path.
    
    Args:
        filename: Name of the blob/file in Azure Blob Storage
        download_path: Local path where the image should be saved
        
    Returns:
        Dictionary with download result:
        - {"filename": str, "download_path": str, "status": "success"}
        - {"filename": str, "error": str, "status": "failed"}
    """
    try:
        result = download_from_azure_blob(filename, download_path)
        
        if result["status"] == "success":
            logger.info(f"Downloaded {filename} from Azure Blob Storage to {download_path}")
            return {
                "filename": filename,
                "download_path": download_path,
                "status": "success"
            }
        else:
            return {
                "filename": filename,
                "status": "failed",
                "error": result["error"]
            }
        
    except Exception as e:
        error_msg = f"Failed to download image: {str(e)}"
        logger.error(f"Error downloading {filename} to {download_path}: {error_msg}")
        return {
            "filename": filename,
            "status": "failed",
            "error": error_msg
        }

if __name__ == "__main__":
    mcp.run(transport='stdio')
