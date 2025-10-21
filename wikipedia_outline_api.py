from flask import Flask, request, jsonify, Response
from bs4 import BeautifulSoup
import requests
import re
from urllib.parse import quote

# Initialize the Flask application
app = Flask(__name__)

# --- CORS Configuration ---
# Manually inject CORS headers to allow requests from any origin
def add_cors_headers(response):
    """Adds necessary CORS headers to the response."""
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

# Apply the CORS function to every response
app.after_request(add_cors_headers)

@app.route('/api/outline', methods=['GET'])
def get_wikipedia_outline():
    """
    API endpoint to fetch a Wikipedia page, extract all headings (H1-H6),
    and return a Markdown outline.
    Query Parameter: ?country=<Country Name>
    """
    country = request.args.get('country')

    if not country:
        return jsonify({
            'error': 'Missing required query parameter: country'
        }), 400

    # 1. Construct the Wikipedia URL
    # Quote the country name to handle spaces and special characters properly
    # The URL for the English Wikipedia page for a country
    encoded_country = quote(country.replace(' ', '_'))
    wikipedia_url = f"https://en.wikipedia.org/wiki/{encoded_country}"

    try:
        # 2. Fetch Wikipedia Content
        # Use a common User-Agent to avoid being blocked
        headers = {'User-Agent': 'WikipediaOutlineGenerator/1.0 (Contact: user@example.com)'}
        response = requests.get(wikipedia_url, headers=headers, timeout=10)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

    except requests.exceptions.HTTPError as e:
        if response.status_code == 404:
            return jsonify({
                'error': f"Wikipedia page not found for '{country}'. URL: {wikipedia_url}"
            }), 404
        return jsonify({
            'error': f"HTTP Error fetching content: {e}"
        }), 500
    except requests.exceptions.RequestException as e:
        return jsonify({
            'error': f"Network Error during content fetch: {e}"
        }), 500

    # 3. Extract Headings and 4. Generate Markdown Outline
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Target the main content area (standard for Wikipedia articles)
    content_div = soup.find('div', {'id': 'content'})
    if not content_div:
        # Fallback to the body content
        content_div = soup.find('div', {'id': 'bodyContent'})
        if not content_div:
             return jsonify({
                'error': "Could not find the main content block on the Wikipedia page."
            }), 500

    # Find all heading tags (H1 to H6) within the content area
    headings = content_div.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])

    outline_lines = ["## Contents\n"] # Start with the required '## Contents' line
    
    for tag in headings:
        tag_name = tag.name  # e.g., 'h1', 'h2'
        
        # Determine the heading level (1 for H1, 2 for H2, etc.)
        level = int(tag_name[1]) 
        
        # Calculate the number of '#' symbols for Markdown
        # H1 = #, H2 = ##, etc.
        markdown_prefix = '#' * level
        
        # Get text content and clean up
        # 1. Get visible text (ignoring edit links/spans)
        text = tag.get_text()
        
        # 2. Clean up common Wikipedia elements like the 'edit' link (usually a span inside H tags)
        # We look for specific IDs/classes used in Wikipedia for cleanup
        edit_span = tag.find('span', class_='mw-editsection')
        if edit_span:
            edit_span.extract() # Remove the edit section before getting the text
            
        # 3. Get the text again after cleanup and remove leading/trailing whitespace
        heading_text = tag.get_text().strip()
        
        # Skip empty headings or the site main heading (which is often already captured by the main h1)
        if not heading_text or heading_text in ['Contents', 'Welcome to Wikipedia']:
             continue

        # Format the line: ## Heading Text
        outline_lines.append(f"{markdown_prefix} {heading_text}")

    # Combine all lines into a single Markdown string
    markdown_outline = '\n'.join(outline_lines)
    
    # If no headings were found other than the standard 'Contents'
    if len(outline_lines) <= 1:
         return jsonify({
            'error': "Successfully fetched the page, but could not extract sufficient content headings."
        }), 404

    # Return the Markdown outline as plain text
    return Response(
        markdown_outline,
        mimetype='text/markdown'
    )

# Removed the if __name__ == '__main__': block for Vercel deployment readiness
