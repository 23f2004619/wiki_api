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
    encoded_country = quote(country.replace(' ', '_'))
    wikipedia_url = f"https://en.wikipedia.org/wiki/{encoded_country}"

    try:
        # 2. Fetch Wikipedia Content
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
        # Fallback to body content
        content_div = soup.find('div', {'id': 'bodyContent'})
        if not content_div:
              return jsonify({
                'error': "Could not find the main content block on the Wikipedia page."
              }), 500

    # Find the main H1 title (usually the article name)
    main_title_tag = content_div.find('h1', {'id': 'firstHeading'})
    outline_lines = []

    # Ensure the main title is the first Level 1 heading
    if main_title_tag and main_title_tag.get_text().strip():
        # Use only the article title for the Level 1 heading
        article_title = main_title_tag.get_text().strip()
        outline_lines.append(f"# {article_title}")
        outline_lines.append(f"## Contents\n") # Add Contents line after the H1

    # Find all subsequent heading tags (H2 to H6) within the content area
    # Note: Wikipedia main sections start at H2
    headings = content_div.find_all(['h2', 'h3', 'h4', 'h5', 'h6'])

    for tag in headings:
        tag_name = tag.name  # e.g., 'h2', 'h3'
        
        # Determine the heading level (2 for H2, 3 for H3, etc.)
        level = int(tag_name[1])
        
        # Calculate the number of '#' symbols for Markdown
        markdown_prefix = '#' * level
        
        # 1. Clean up common Wikipedia elements like the 'edit' link
        edit_span = tag.find('span', class_='mw-editsection')
        if edit_span:
            edit_span.extract() # Remove the edit section before getting the text
            
        # 2. Get the text and clean up
        heading_text = tag.get_text().strip()
        
        # Skip empty headings or known non-content headings
        if not heading_text or heading_text in ['Contents', 'Welcome to Wikipedia', 'See also', 'References', 'External links']:
              continue
              
        # Format the line: ## Heading Text
        outline_lines.append(f"{markdown_prefix} {heading_text}")

    # Combine all lines into a single Markdown string
    markdown_outline = '\n'.join(outline_lines)
    
    # If not enough content headings were found
    if len(outline_lines) <= 1:
          return jsonify({
            'error': "Successfully fetched the page, but could not extract sufficient content headings."
        }), 404

    # Return the Markdown outline as plain text
    return Response(
        markdown_outline,
        mimetype='text/markdown'
    )
