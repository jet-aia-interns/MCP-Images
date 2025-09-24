# Google Images Search Integration

This MCP server now includes Google Images search functionality that allows you to:

1. **Search Google Images** - Find images using natural language queries
2. **Get Direct URLs** - Receive direct image URLs that display the actual images
3. **Select Best Images** - Let the LLM choose the most appropriate image(s)
4. **Upload to Azure** - Automatically download and upload selected images to Azure Blob Storage

## New Tool: `search_google_images`

### Parameters:
- `search_query` (str): The search term to look for images (e.g., "red sunset over ocean")
- `max_results` (int): Maximum number of image URLs to return (default: 10, max: 20)

### Returns:
A list of dictionaries containing:
- `url` (str): Direct URL to the image
- `title` (str): Image title/filename
- `source` (str): Source website URL
- `status` (str): "success" or "failed"

### Example Usage:

```python
# Search for images
results = await search_google_images("beautiful mountain landscape", max_results=5)

# Results will look like:
[
    {
        "url": "https://example.com/image1.jpg",
        "title": "Mountain sunset landscape",
        "source": "https://example.com",
        "status": "success"
    },
    # ... more results
]
```

## Complete Workflow Example:

1. **LLM searches for images:**
   ```
   search_google_images("cute puppies playing", max_results=10)
   ```

2. **LLM reviews the results and selects the best image:**
   ```
   The search returned 10 images. I'll select the first one:
   https://example.com/cute-puppy.jpg
   ```

3. **LLM uploads the selected image to Azure:**
   ```
   upload_single_image_to_azure("https://example.com/cute-puppy.jpg")
   ```

4. **LLM gets the final Azure URL and markdown:**
   ```
   ![cute-puppy_20250910_123456.jpg](https://aiainternal.blob.core.windows.net/image-mcp/cute-puppy_20250910_123456.jpg?...)
   ```

## Technical Details:

### Search Method:
- Uses HTTP requests to fetch Google Images search results
- Supports both old (`tbm=isch`) and new (`udm=2`) Google Images URL formats
- Automatically handles redirects
- Validates image URLs to ensure they work
- Filters out unwanted domains (gstatic, ggpht, etc.)

### Fallback Support:
- If Selenium is available, it can use browser automation for more accurate results
- Falls back to HTTP-based scraping if Selenium is not available
- Both methods return the same data structure

### Image Validation:
- Performs HEAD requests to validate image URLs
- Checks for proper image content-type headers
- Filters out broken or invalid URLs

## Installation Requirements:

The server will work with just the basic dependencies. For enhanced functionality:

```bash
# Basic (HTTP-based scraping):
uv add httpx

# Enhanced (browser-based scraping):
uv add selenium
# Also requires Chrome browser and chromedriver
```

## Usage Scenarios:

1. **Blog Post Creation**: Search for relevant images to accompany blog posts
2. **Content Creation**: Find images for presentations, documents, or websites
3. **Product Research**: Search for product images or inspiration
4. **Design Work**: Find reference images or design elements

## Benefits:

- **No Copyright Issues**: Returns direct URLs to publicly available images
- **High Quality**: Gets full-resolution images, not thumbnails
- **Automated Workflow**: Complete integration from search to cloud storage
- **LLM-Friendly**: Structured data that LLMs can easily process and choose from
- **Reliable**: Multiple fallback methods ensure consistent functionality

## Example LLM Interaction:

```
User: "Find me a nice image of a sunset over the ocean and save it to Azure"

LLM: "I'll search for sunset images and upload the best one to Azure for you."

1. search_google_images("sunset over ocean", max_results=5)
2. [Reviews the 5 results and selects the best one]
3. upload_single_image_to_azure(selected_url)
4. "Here's your sunset image: ![sunset_image.jpg](azure_url)"
```

This creates a seamless experience where the LLM can find, evaluate, and save images automatically based on user requests.
