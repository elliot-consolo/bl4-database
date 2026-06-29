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

def remove_duplicates(lst):
    """
    Removes duplicates from a list while preserving the original order.
    """
    seen = set()
    result = []
    for item in lst:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result

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

        locations = {}
        all_regions = []
        all_areas = []

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
                temp_df = temp_df.replace(r'^\s*$', np.nan, regex=True).infer_objects(copy=False)

                #take region after comma if it exists, otherwise take name
                for idx, location in temp_df['Location'].items():
                    if pd.notnull(location) and pd.notnull(idx):
                        parts = location.split(',')
                        if len(parts) > 1:
                            temp_df.at[idx, 'Location'] = parts[1].strip()
                            all_areas.append(parts[0].strip())
                            all_regions.append(parts[1].strip())
                        else:
                            temp_df.at[idx, 'Location'] = parts[0].strip()
                            all_regions.append(parts[0].strip())
                sheet_regions = temp_df['Location'].unique().tolist()

                # remove actual NaN values and any empty/whitespace-only strings
                sheet_regions = [str(x).strip() for x in sheet_regions if pd.notnull(x) and str(x).strip() != '']

                # clean areas list as well
                all_areas = [str(x).strip() for x in all_areas if pd.notnull(x) and str(x).strip() != '']
                all_areas = remove_duplicates(all_areas)

                all_regions = [str(x).strip() for x in all_regions if pd.notnull(x) and str(x).strip() != '']
                all_regions = remove_duplicates(all_regions)

                location_order = ['Fadefields', 'Carcadia Burn', 'Terminus Range', 'Dominion', 'The Whispering Glacier', 'The Demon\'s Domain']
                order_lookup = {item: index for index, item in enumerate(location_order)}

                all_regions = sorted(all_regions, key=lambda x: order_lookup.get(x, len(location_order)))

                filter_options['Location'] = sorted(sheet_regions, key=lambda x: order_lookup.get(x, len(location_order)))
            

            all_filter_options[sheet_slug] = filter_options

        locations['regions'] = all_regions
        locations['areas'] = all_areas
        locations['region_slugs'] = [slugify(region) for region in all_regions]

        return all_sheets_data, all_sheet_info, all_filter_options, locations
    except FileNotFoundError:
        print("Error: spreadsheet not found. Please ensure the file is in the same directory.")
        return []    

all_sheets_data, all_sheet_info, all_filter_options, locations = get_spreadsheet_data()
available_sheets = list(all_sheets_data.keys())

def filter_option_text(filter, option):
    if filter == "Elements":
        if option == "N":
            return "No Element"
        elif option == "F":
            return "Incendiary"
        elif option == "S":
            return "Shock"
        elif option == "C":
            return "Corrosive"
        elif option == "R":
            return "Radiation"
        elif option == "Y":
            return "Cryo"
    elif filter == "Type":
        if option == "AR":
            return "Assault Rifle"
        elif option == "SMG":
            return "Submachine Gun"
        elif option == "SG":
            return "Shotgun"
    return option

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
        return render_template('sheet_data.html',sheet_info=all_sheet_info[sheet_slug], sheet_data=sheet_data, filter_options=all_filter_options[sheet_slug], trie_data=trie_data, filter_option_text=filter_option_text)
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

@app.route('/api/data/locations/<string:location_slug>', methods=['GET'])
def display_location(location_slug):
    trie_data = get_all_names_for_trie()
    region_name, region_slug = next(((region, slug) for region, slug in zip(locations['regions'], locations['region_slugs']) if slug == location_slug), None)
    
    if region_name:
        location_data = {
            'region_name': region_name,
            'region_slug': region_slug
        }
        items_in_region = []
        sources_in_region = []
        for sheet_slug, sheet_data in all_sheets_data.items():
            if sheet_slug != 'sources':
                for item in sheet_data:
                    if region_name in item['Location']:
                        item['sheet'] = all_sheet_info[sheet_slug]['original_name']
                        item['sheet-slug'] = all_sheet_info[sheet_slug]['slug']
                        item['url'] = url_for('display_item', sheet_slug=sheet_slug, name_slug=item['name_slug'])
                        items_in_region.append(item)
            else:
                for source in sheet_data:
                    if region_name in source['Location']:
                        source['sheet'] = all_sheet_info[sheet_slug]['original_name']
                        source['sheet-slug'] = all_sheet_info[sheet_slug]['slug']
                        source['url'] = url_for('display_item', sheet_slug=sheet_slug, name_slug=source['name_slug'])
                        sources_in_region.append(source)
        
        return render_template('location_data.html', location_data=location_data, items_in_region=items_in_region, sources_in_region=sources_in_region, trie_data=trie_data)
    
    abort(404, description=f"Region '{location_slug}' not found")
    
# --- Frontend route ---
@app.route('/', methods=['GET'])
def index():
    trie_data = get_all_names_for_trie()
    return render_template('index.html', sheet_info=all_sheet_info, trie_data=trie_data, locations=locations)

@app.route('/api/sheets', methods=['GET'])
def getSheets():
    return jsonify(available_sheets)

if __name__ == '__main__':
    app.run(debug=True)