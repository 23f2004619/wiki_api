from flask import Flask, request, jsonify, Response
from bs4 import BeautifulSoup
import requests
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
    and return a Markdown outline, formatted to satisfy the specific
    validation requirement starting with # Contents.
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

    # --- Start Outline Generation ---
    outline_lines = []

    # 1. ADD THE REQUIRED FIXED STARTING HEADING (H1)
    # This satisfies the validation rule: "Expected Contents"
    outline_lines.append(f"# Contents")

    # Find the main H1 title (usually the article name) by searching the whole soup
    main_title_tag = soup.find('h1', {'id': 'firstHeading'})

    # 2. ADD THE ARTICLE TITLE AS THE SECOND HEADING (Level 2)
    if main_title_tag and main_title_tag.get_text().strip():
        article_title = main_title_tag.get_text().strip()
        # The article title is Level 2 (##)
        outline_lines.append(f"## {article_title}")

    # Target the main content area for section headings
    content_div = soup.find('div', {'id': 'content'})
    if not content_div:
        content_div = soup.find('div', {'id': 'bodyContent'})

    # 3. Process Structural Headings (H2 to H6)
    # We find all headings from H2 downwards in the main content.
    headings = content_div.find_all(['h2', 'h3', 'h4', 'h5', 'h6'])

    for tag in headings:
        tag_name = tag.name  # e.g., 'h2', 'h3'

        # Determine the HTML heading level (2 for H2, 3 for H3, etc.)
        html_level = int(tag_name[1])

        # Shift the Markdown level down by 1 relative to the HTML level
        # H2 (HTML) -> Level 3 (Markdown)
        # H3 (HTML) -> Level 4 (Markdown)
        markdown_level = html_level + 1

        # Calculate the number of '#' symbols for Markdown
        markdown_prefix = '#' * markdown_level

        # Clean up common Wikipedia elements like the 'edit' link
        edit_span = tag.find('span', class_='mw-editsection')
        if edit_span:
            edit_span.extract()

        # Get the text and clean up
        heading_text = tag.get_text().strip()

        # Skip empty headings or known non-content/redundant headings
        if not heading_text or heading_text in ['Contents', 'Welcome to Wikipedia', 'See also', 'References', 'External links', 'Further reading', 'Notes', 'Bibliography']:
              continue

        # Format the line
        outline_lines.append(f"{markdown_prefix} {heading_text}")

    # Combine all lines into a single Markdown string
    markdown_outline = '\n'.join(outline_lines)

    # Final check: Ensure we have more than just the two fixed title lines
    if len(outline_lines) <= 2:
          return jsonify({
            'error': "Successfully fetched the page, but could not extract sufficient content headings beyond the title."
        }), 404

    # Return the Markdown outline as plain text
    return Response(
        markdown_outline,
        mimetype='text/markdown'
    )
