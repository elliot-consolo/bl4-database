from flask import Flask, jsonify, abort, render_template, url_for
from urllib.parse import quote_plus, unquote_plus
import re
import pandas as pd
import numpy as np

app = Flask(__name__, static_folder='static', static_url_path='/static')

app_node_modules = Flask(__name__, static_folder='node_modules', static_url_path='/node_modules')

app.add_url_rule('/node_modules/<path:filename>', endpoint='node_modules', view_func=app_node_modules.send_static_file)


SHEET_DESCRIPTIONS = {
    'Weapons': 'Weapons Info',
    'Shields': 'Shields Info'
}

ABBREVIATIONS = {
    'AR': 'Assault Rifle',
    'RL': 'Launcher',
    'SG': 'Shotgun'
}

ELEMENT_IMG = {
    'N': 'images/elements/no.png',
    'F': 'images/elements/fire.png',
    'S': 'images/elements/shock.png',
    'C': 'images/elements/corrosive.png',
    'R': 'images/elements/radiation.png',
    'Y': 'images/elements/cryo.png'
}

def slugify(text):
    """
    Converts a string into a URL-safe slug.
    - Converts to lowercase.
    - Replaces spaces and non-alphanumeric characters with hyphens.
    """
    text = str(text).lower()
    text = re.sub(r'[^a-z0-9\s-]', '', text) # Remove special characters
    text = re.sub(r'[\s-]+', '-', text).strip('-') # Replace spaces with single hyphen
    return text

def expand_abbreviation(abbrev):
    return ABBREVIATIONS.get(abbrev, abbrev)

app.jinja_env.filters['expand'] = expand_abbreviation

def get_element_image(element):
    image_path = ELEMENT_IMG.get(element)
    if image_path:
        image_url = url_for('static', filename=image_path)
        return f'<img src="{image_url}" alt="{element}" class="img-fluid" style="max-height: 25px;">'
    return element

app.jinja_env.filters['element_img'] = get_element_image

def get_item_image(sheetName, item):
    item = item.replace('\'','_')
    image_path = "images/" + sheetName + "/" + item + ".jpg"
    if image_path:
        image_url = url_for('static', filename=image_path)
        return image_url
    return item

app.jinja_env.filters['item_img'] = get_item_image


@app.route('/spreadsheet-data', methods=['GET'])
def get_spreadsheet_data():
    try:
        # Assumes data.xlsx is in the same directory as app.py
        xls = pd.read_excel('BL4_Legendary_Data.xlsx', sheet_name=None)
    
        all_sheets_data = {}
        all_sheet_info = {}
        all_filter_options = {}

        for sheet_name,df in xls.items():
            df = df.replace(np.nan, '') 
            sheet_slug = slugify(sheet_name)

            if 'Name' not in df.columns:
                print(f"Warning: 'Name' column not found in sheet '{sheet_name}'. Skipping.")
                continue
            
            df['name_slug'] = df['Name'].str.lower().str.replace(' ', '-')
            
            df['name_slug'] = df['Name'].apply(slugify)
            all_sheets_data[sheet_slug] = df.to_dict(orient='records')
            description = SHEET_DESCRIPTIONS.get(sheet_name, "Description unavailable")

            all_sheet_info[sheet_slug] = {'original_name': sheet_name, 'slug': sheet_slug, 'description': description}

            filter_options = {}
            if 'Type' in df.columns:
                filter_options['Type'] = sorted(df['Type'].unique().tolist())
            if 'Manufacturer' in df.columns:
                filter_options['Manufacturer'] = sorted(df['Manufacturer'].unique().tolist())
            if 'Elements' in df.columns:
                text = df['Elements'].astype(str)
                text_str = ''.join(text)
                unique_elements = set(text_str)
                
                element_order = ['N', 'F', 'S', 'C', 'R', 'Y']
                order_lookup = {item: index for index, item in enumerate(element_order)}

                filter_options['Elements'] = sorted(unique_elements, key=lambda element: order_lookup[element])
            if 'Class' in df.columns:
                filter_options['Class'] = sorted(df['Class'].unique().tolist())
            if 'Location' in df.columns:
                #create temp copy of Location with new rows for '|' locations
                temp_df = df.assign(Location=df['Location'].str.split('|')).explode('Location')
                #take region after comma if it exists, otherwise take name
                regions = temp_df['Location'].apply(lambda x: x.split(',', 1)[1].strip() if pd.notnull(x) and ',' in str(x) else str(x).strip())
                
                filter_options['Location'] = sorted(regions.unique().tolist())

            all_filter_options[sheet_slug] = filter_options

        return all_sheets_data, all_sheet_info, all_filter_options
    except FileNotFoundError:
        print("Error: spreadsheet not found. Please ensure the file is in the same directory.")
        return []    

all_sheets_data, all_sheet_info, all_filter_options = get_spreadsheet_data()
available_sheets = list(all_sheets_data.keys())

def get_all_names_for_trie():
    all_names_data = []
    for sheet_slug, sheet_data in all_sheets_data.items():
        for row in sheet_data:
            # Store the name and the URL slug for linking
            all_names_data.append({
                'name': row['Name'],
                'url': url_for('display_item', sheet_slug=sheet_slug, name_slug=row['name_slug'])
            })
    return all_names_data

def get_items_in_location(location):
    items_in_location = []

    data = {key: value for key, value in all_sheets_data.items() if key != 'sources'}
    
    for sheet_slug, sheet_data in data.items():
        for item in sheet_data:
            if item['Location'] == location:
                item['sheet'] = all_sheet_info[sheet_slug]['original_name']
                item['sheet-slug'] = all_sheet_info[sheet_slug]['slug']
                item['url'] = url_for('display_item', sheet_slug=sheet_slug, name_slug=item['name_slug'])
                items_in_location.append(item)
    return items_in_location

def get_source_drops(source):
    source_drops = []

    data = {key: value for key, value in all_sheets_data.items() if key != 'sources'}

    for sheet_slug, sheet_data in data.items():
        for item in sheet_data:
            item['sheet'] = all_sheet_info[sheet_slug]['original_name']
            item['sheet-slug'] = all_sheet_info[sheet_slug]['slug']
            
            if '|' in item['Source']:
                temp_sources = item['Source'].split('|')
                sources = [item.strip() for item in temp_sources]
                
                if source in sources:
                    
                    item['url'] = url_for('display_item', sheet_slug=sheet_slug, name_slug=item['name_slug'])
                    source_drops.append(item)
            elif item['Source'] == source:
                
                item['url'] = url_for('display_item', sheet_slug=sheet_slug, name_slug=item['name_slug'])
                source_drops.append(item)
    return source_drops
    
def get_source_location(source):
    for item in all_sheets_data['sources']:
        if item['Name'] == source:
            return item['Location']

@app.route('/api/data/<string:sheet_slug>', methods=['GET'])
def display_sheet(sheet_slug):
    trie_data = get_all_names_for_trie()

    if sheet_slug in all_sheets_data:
        sheet_data = all_sheets_data[sheet_slug]
        return render_template('sheet_data.html',sheet_info=all_sheet_info[sheet_slug], sheet_data=sheet_data, filter_options=all_filter_options[sheet_slug], trie_data=trie_data)
    abort(404, description=f"Sheet '{sheet_slug}' not found")

# --- API endpoint to get data for a specific sheet ---
@app.route('/api/data/<string:sheet_slug>/<string:name_slug>', methods=['GET'])
def display_item(sheet_slug, name_slug):
    trie_data = get_all_names_for_trie()

    if sheet_slug == 'sources':
        search_slug = unquote_plus(name_slug)
        source_data = next((item for item in all_sheets_data[sheet_slug] if item['name_slug'] == search_slug),None)
        if source_data:
            source_drops = get_source_drops(source_data['Name'])
            
            

            location = source_data['Location']
            items_in_location = [item for item in get_items_in_location(location) if item not in source_drops]
            
            return render_template('source_data.html', sheet_info=all_sheet_info[sheet_slug], source_data=source_data, trie_data=trie_data, items_in_location=items_in_location, source_drops=source_drops)
        
    elif sheet_slug in all_sheets_data:
        search_slug = unquote_plus(name_slug)
        item_data = next((item for item in all_sheets_data[sheet_slug] if item['name_slug'] == search_slug),None)
        if item_data:
            location = item_data['Location']
            
            items_in_location = [item for item in get_items_in_location(location) if item != item_data]

            sources = []
            if '|' in item_data['Source']:
                temp_item_sources = item_data['Source'].split('|')
                item_sources = [item.strip() for item in temp_item_sources]
                
                for source in item_sources:
                    sources.append({
                        'name': source,
                        'location': get_source_location(source),
                        'slug': slugify(source)
                    })
            else:
                sources.append({
                        'name': item_data['Source'],
                        'location': get_source_location(item_data['Source']),
                        'slug': slugify(item_data['Source'])
                    })
            
            return render_template('item_data.html', sheet_info=all_sheet_info[sheet_slug], item_data=item_data, trie_data=trie_data, items_in_location=items_in_location, sources=sources)
        abort(404, description=f"'{name_slug}' not found")
    
    abort(404, description=f"Sheet '{sheet_slug}' not found")

# --- Frontend route ---
@app.route('/', methods=['GET'])
def index():
    trie_data = get_all_names_for_trie()
    return render_template('index.html', sheet_info=all_sheet_info, trie_data=trie_data)

@app.route('/api/sheets', methods=['GET'])
def getSheets():
    return jsonify(available_sheets)

if __name__ == '__main__':
    app.run(debug=True)