import json
import os
import itertools
import pandas as pd
import networkx as nx
import plotly.graph_objects as go
import streamlit as st
import requests
import time
from streamlit.components.v1 import html

DATA_FILE = 'citation_data3.json'

# Initialize session state
if 'selected_node' not in st.session_state:
    st.session_state.selected_node = None

def handle_node_click(trace, points, state):
    if len(points.point_inds) > 0:
        clicked_node = trace.customdata[points.point_inds[0]]
        if clicked_node == st.session_state.selected_node:
            st.session_state.selected_node = None
        else:
            st.session_state.selected_node = clicked_node
        st.rerun()

# ----------------- API Integration -------------------
def fetch_paper_metadata(doi):
    """Fetch paper metadata from Crossref API"""
    try:
        headers = {'User-Agent': 'Citagraph/1.0 (mailto:your-email@example.com)'}
        response = requests.get(f'https://api.crossref.org/works/{doi}', headers=headers)
        if response.status_code == 200:
            data = response.json()['message']
            
            # Get authors list
            authors = data.get('author', [])
            first_author = authors[0].get('family', 'Unknown') if authors else 'Unknown'
            
            # Try to identify PI (last author)
            pi = 'Unknown'
            if len(authors) > 1:  # If there are multiple authors
                pi = authors[-1].get('family', 'Unknown')  # Get last author's name
                
                # Check for corresponding author if available
                for author in authors:
                    if author.get('sequence') == 'additional' and author.get('corresponding', False):
                        pi = author.get('family', pi)
                        break
            
            return {
                'title': data.get('title', [''])[0],
                'author': first_author,
                'pi': pi,
                'year': str(data.get('published-print', {}).get('date-parts', [['']])[0][0]),
                'url': f"https://doi.org/{doi}",
                'references': [ref.get('DOI', '') for ref in data.get('reference', []) if ref.get('DOI')],
                'all_authors': [f"{author.get('given', '')} {author.get('family', '')}" for author in authors]
            }
    except Exception as e:
        st.error(f"Error fetching metadata: {str(e)}")
    return None

def add_paper_with_references(graph, display_names, paper_info, paper_links, doi):
    """Add a paper and connect it to existing papers in our library that it cites"""
    metadata = fetch_paper_metadata(doi)
    if metadata:
        # Add the main paper
        paper_id = doi
        graph.add_node(paper_id)
        display_names[paper_id] = metadata['title']
        
        # Store paper information including all authors
        paper_info[paper_id] = {
            'author': metadata['author'],
            'pi': metadata['pi'],
            'year': metadata['year'],
            'all_authors': metadata.get('all_authors', [])
        }
        paper_links[paper_id] = metadata['url']
        
        # Show author information
        st.info(f"First Author: {metadata['author']}")
        st.info(f"Detected PI (Last Author): {metadata['pi']}")
        st.info(f"All Authors: {', '.join(metadata.get('all_authors', []))}")
        
        # Allow user to correct PI if needed
        corrected_pi = st.text_input("Correct PI if needed:", value=metadata['pi'])
        if corrected_pi != metadata['pi']:
            paper_info[paper_id]['pi'] = corrected_pi
        
        # Check references against existing papers and add connections
        existing_papers = set(graph.nodes())
        citations_found = 0
        
        for ref_doi in metadata['references']:
            if ref_doi in existing_papers:
                graph.add_edge(paper_id, ref_doi)
                citations_found += 1
        
        if citations_found > 0:
            st.info(f"Found {citations_found} citation{'s' if citations_found > 1 else ''} to existing papers in the library")
        else:
            st.info("No citations found to existing papers in the library")
        
        return True
    return None

# ----------------- Graph Loading & Saving -------------------
def load_graph_from_json(filename):
    graph = nx.DiGraph()
    display_names = {}
    paper_info = {}
    paper_links = {}
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            data = json.load(f)
            for paper_id, info in data.get('papers', {}).items():
                graph.add_node(paper_id)
                display_names[paper_id] = info.get('title', paper_id)
                paper_info[paper_id] = {
                    'author': info.get('author', 'Unknown'),
                    'pi': info.get('pi', 'Unknown'),
                    'year': info.get('year', 'Unknown')
                }
                paper_links[paper_id] = info.get('url', '')
            for paper_id, cited_ids in data.get('citations', {}).items():
                for cited_id in cited_ids:
                    graph.add_edge(paper_id, cited_id)
    return graph, display_names, paper_info, paper_links

def save_graph_to_json(graph, display_names, paper_info, paper_links, filename):
    data = {'papers': {}, 'citations': {}}
    for node in graph.nodes():
        data['papers'][node] = {
            'title': display_names[node],
            'author': paper_info[node]['author'],
            'pi': paper_info[node]['pi'],
            'year': paper_info[node]['year'],
            'url': paper_links[node]
        }
        data['citations'][node] = list(graph.successors(node))
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)

# ----------------- Color Mapping -------------------
def get_decade_color(year):
    try:
        decade = (int(year) // 10) * 10
        # Rainbow progression from red (oldest) to violet (newest)
        color_map = {
            1960: 'rgb(255, 0, 0)',      # Red
            1970: 'rgb(255, 127, 0)',    # Orange
            1980: 'rgb(255, 255, 0)',    # Yellow
            1990: 'rgb(0, 255, 0)',      # Green
            2000: 'rgb(0, 0, 255)',      # Blue
            2010: 'rgb(75, 0, 130)',     # Indigo
            2020: 'rgb(148, 0, 211)',    # Violet
            2030: 'rgb(200, 0, 255)'     # Future papers (purple)
        }
        return color_map.get(decade, 'rgb(128, 128, 128)')  # Gray for unknown decades
    except:
        return 'rgb(128, 128, 128)'  # Gray for invalid years

# Define a list of distinct colors for authors
AUTHOR_COLORS = [
    'rgb(255, 99, 71)',    # Tomato
    'rgb(34, 139, 34)',    # Forest Green
    'rgb(30, 144, 255)',   # Dodger Blue
    'rgb(255, 215, 0)',    # Gold
    'rgb(138, 43, 226)',   # Blue Violet
    'rgb(255, 105, 180)',  # Hot Pink
    'rgb(0, 128, 128)',    # Teal
    'rgb(255, 140, 0)',    # Dark Orange
    'rgb(147, 112, 219)',  # Medium Purple
    'rgb(0, 100, 0)',      # Dark Green
    'rgb(205, 92, 92)',    # Indian Red
    'rgb(70, 130, 180)',   # Steel Blue
    'rgb(218, 112, 214)',  # Orchid
    'rgb(0, 139, 139)',    # Dark Cyan
    'rgb(255, 69, 0)',     # Red Orange
    'rgb(72, 61, 139)',    # Dark Slate Blue
    'rgb(184, 134, 11)',   # Dark Goldenrod
    'rgb(139, 69, 19)',    # Saddle Brown
    'rgb(47, 79, 79)',     # Dark Slate Gray
    'rgb(199, 21, 133)'    # Medium Violet Red
]

def get_author_color(author, color_map):
    """Assign a unique color to each author"""
    if author not in color_map:
        # Get all currently used colors
        used_colors = set(color_map.values())
        # Find the first available color that hasn't been used
        for color in AUTHOR_COLORS:
            if color not in used_colors:
                color_map[author] = color
                return color
        # If all colors are used, create a slightly modified version of an existing color
        base_color = AUTHOR_COLORS[len(color_map) % len(AUTHOR_COLORS)]
        rgb_values = [int(x) for x in base_color[4:-1].split(',')]
        # Modify the RGB values slightly
        modified_rgb = [
            (v + 30 * (len(color_map) // len(AUTHOR_COLORS))) % 256 
            for v in rgb_values
        ]
        color_map[author] = f'rgb({modified_rgb[0]}, {modified_rgb[1]}, {modified_rgb[2]})'
    return color_map[author]

# ----------------- Graph Plotting -------------------
def draw_graph_plotly(graph, display_names, paper_info, layout_choice, color_mode):
    # Store the selected node in session state if it doesn't exist
    if 'selected_node' not in st.session_state:
        st.session_state.selected_node = None

    # Determine the layout for graph plotting
    if layout_choice == "spring":
        pos = nx.spring_layout(graph, seed=42)
    elif layout_choice == "circular":
        pos = nx.circular_layout(graph)
    elif layout_choice == "kamada-kawai":
        pos = nx.kamada_kawai_layout(graph)
    elif layout_choice == "random":
        pos = nx.random_layout(graph)
    elif layout_choice == "fruchterman-reingold":
        pos = nx.fruchterman_reingold_layout(graph)
    else:
        pos = nx.spring_layout(graph, seed=42)

    color_groups = {}
    color_map = {}

    if color_mode == "First Author":
        if 'first_author_colors' not in st.session_state:
            st.session_state.first_author_colors = {}
        color_map = st.session_state.first_author_colors
    elif color_mode == "Principal Investigator":
        if 'pi_colors' not in st.session_state:
            st.session_state.pi_colors = {}
        color_map = st.session_state.pi_colors

    # Get connected nodes if there's a selection
    connected_nodes = set()
    if st.session_state.selected_node:
        connected_nodes = set(graph.successors(st.session_state.selected_node)) | set(graph.predecessors(st.session_state.selected_node))
        connected_nodes.add(st.session_state.selected_node)

    # Create edges with different colors based on selection
    edge_traces = []
    
    # Function to create edge trace
    def create_edge_trace(edges, color, width):
        edge_x, edge_y = [], []
        for src, dst in edges:
            x0, y0 = pos[src]
            x1, y1 = pos[dst]
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])
        
        return go.Scatter(
            x=edge_x, y=edge_y,
            line=dict(width=width, color=color),
            hoverinfo='none',
            mode='lines',
            showlegend=False
        )

    # Split edges into highlighted and non-highlighted
    if st.session_state.selected_node:
        highlighted_edges = [(u, v) for u, v in graph.edges() 
                           if u == st.session_state.selected_node or v == st.session_state.selected_node]
        normal_edges = [(u, v) for u, v in graph.edges() 
                       if u != st.session_state.selected_node and v != st.session_state.selected_node]
        
        # Add normal edges (thinner, lighter)
        if normal_edges:
            edge_traces.append(create_edge_trace(normal_edges, 'rgba(180,180,180,0.2)', 1))
        
        # Add highlighted edges (thicker, darker)
        if highlighted_edges:
            edge_traces.append(create_edge_trace(highlighted_edges, 'rgba(50,50,50,0.8)', 2))
    else:
        # If no node is selected, show all edges normally
        edge_traces.append(create_edge_trace(graph.edges(), 'rgba(128,128,128,0.6)', 1))

    # Create node traces with customdata for click events
    node_traces = []
    
    # For decade mode, create traces in chronological order
    if color_mode == "Decade":
        # Create a dictionary to store nodes by decade
        decade_groups = {}
        for node in graph.nodes():
            year = paper_info.get(node, {}).get('year', 'Unknown')
            try:
                decade = (int(year) // 10) * 10
                label = f"{decade}s"
            except:
                decade = float('inf')  # Put unknown at the end
                label = "Unknown"
            
            if label not in decade_groups:
                decade_groups[label] = {
                    'x': [], 'y': [], 'text': [], 'color': get_decade_color(year),
                    'size': [], 'opacity': [], 'customdata': []
                }
            
            x, y = pos[node]
            title = display_names.get(node, node)
            first_author = paper_info.get(node, {}).get('author', 'Unknown')
            pi = paper_info.get(node, {}).get('pi', 'Unknown')
            
            # Create hover text with just first author and PI information
            text = f"{title}<br>First Author: {first_author}<br>PI: {pi}<br>Year: {year}<br><b>Paper ID:</b> {node}"
            
            # Adjust node size and opacity based on selection
            size = 12
            opacity = 1.0
            if st.session_state.selected_node:
                if node == st.session_state.selected_node:
                    size = 20  # Make selected node larger
                    opacity = 1.0
                elif node in connected_nodes:
                    size = 16  # Make connected nodes slightly larger
                    opacity = 0.9
                else:
                    size = 12  # Keep normal size for unconnected nodes
                    opacity = 0.3  # Make unconnected nodes slightly transparent
            
            decade_groups[label]['x'].append(x)
            decade_groups[label]['y'].append(y)
            decade_groups[label]['text'].append(text)
            decade_groups[label]['size'].append(size)
            decade_groups[label]['opacity'].append(opacity)
            decade_groups[label]['customdata'].append(node)
        
        # Add traces in chronological order
        sorted_decades = sorted([d for d in decade_groups.keys() if d != "Unknown"])
        if "Unknown" in decade_groups:
            sorted_decades.append("Unknown")
        
        for decade in sorted_decades:
            group = decade_groups[decade]
            node_trace = go.Scatter(
                x=group['x'], y=group['y'],
                mode='markers',
                hoverinfo='text',
                text=group['text'],
                customdata=group['customdata'],
                marker=dict(
                    color=group['color'],
                    size=group['size'],
                    opacity=group['opacity'],
                    line=dict(width=2, color='DarkSlateGrey')
                ),
                name=decade
            )
            node_traces.append(node_trace)
    
    else:  # First Author or PI mode
        for node in graph.nodes():
            first_author = paper_info.get(node, {}).get('author', 'Unknown')
            pi = paper_info.get(node, {}).get('pi', 'Unknown')
            year = paper_info.get(node, {}).get('year', 'Unknown')
            
            if color_mode == "First Author":
                label = first_author
                color = get_author_color(first_author, color_map)
            else:  # Principal Investigator mode
                label = pi
                color = get_author_color(pi, color_map)

            if label not in color_groups:
                color_groups[label] = {
                    'x': [], 'y': [], 'text': [], 'color': color,
                    'size': [], 'opacity': [], 'customdata': []
                }

            x, y = pos[node]
            title = display_names.get(node, node)
            
            # Create hover text with just first author and PI information
            text = f"{title}<br>First Author: {first_author}<br>PI: {pi}<br>Year: {year}<br><b>Paper ID:</b> {node}"
            
            # Adjust node size and opacity based on selection
            size = 12
            opacity = 1.0
            if st.session_state.selected_node:
                if node == st.session_state.selected_node:
                    size = 20  # Make selected node larger
                    opacity = 1.0
                elif node in connected_nodes:
                    size = 16  # Make connected nodes slightly larger
                    opacity = 0.9
                else:
                    size = 12  # Keep normal size for unconnected nodes
                    opacity = 0.3  # Make unconnected nodes slightly transparent
            
            color_groups[label]['x'].append(x)
            color_groups[label]['y'].append(y)
            color_groups[label]['text'].append(text)
            color_groups[label]['size'].append(size)
            color_groups[label]['opacity'].append(opacity)
            color_groups[label]['customdata'].append(node)

        # Create node traces for author/PI mode
        for label, group in color_groups.items():
            node_trace = go.Scatter(
                x=group['x'], y=group['y'],
                mode='markers',
                hoverinfo='text',
                text=group['text'],
                customdata=group['customdata'],
                marker=dict(
                    color=group['color'],
                    size=group['size'],
                    opacity=group['opacity'],
                    line=dict(width=2, color='DarkSlateGrey')
                ),
                name=label
            )
            node_traces.append(node_trace)

    # Create the figure with all traces
    fig = go.Figure(data=edge_traces + node_traces)

    # Update layout with click event handling
    fig.update_layout(
        title='',
        font=dict(size=16, color='black', family='Times New Roman'),
        title_font=dict(size=24, color='black', family='Times New Roman'),
        showlegend=True,
        hovermode='closest',
        margin=dict(b=10, l=10, r=10, t=40),
        xaxis=dict(showgrid=False, zeroline=False, visible=False),
        yaxis=dict(showgrid=False, zeroline=False, visible=False),
        plot_bgcolor='white',
        paper_bgcolor='white',
        legend=dict(
            font=dict(size=14, color='black', family='Times New Roman'),
            bgcolor='white',
            bordercolor='black',
            borderwidth=1
        ),
        dragmode='pan'  # Make it easier to click nodes
    )

    return fig

# ----------------- Streamlit UI -------------------
st.set_page_config(layout='wide')
st.title("Citagraph3")

# Initialize session state for click handling
if 'clicked_node' not in st.session_state:
    st.session_state.clicked_node = None

# Load Graph Data
graph, display_names, paper_info, paper_links = load_graph_from_json(DATA_FILE)

# Sidebar Controls
with st.sidebar:
    st.header("Paper Management")
    
    # Auto-Add Paper with Citations
    with st.expander("Auto-Add Paper with Citations", expanded=True):
        paper_doi = st.text_input("Enter Paper DOI")
        if st.button("Fetch and Add Paper"):
            if paper_doi:
                with st.spinner('Fetching paper data...'):
                    if add_paper_with_references(graph, display_names, paper_info, paper_links, paper_doi):
                        save_graph_to_json(graph, display_names, paper_info, paper_links, DATA_FILE)
                        st.success("Paper and its citations added successfully!")
                    else:
                        st.error("Failed to fetch paper data. Please check the DOI and try again.")
            else:
                st.warning("Please enter a DOI")

    # Edit/Delete Paper
    with st.expander("Edit/Delete Paper", expanded=False):
        if graph.number_of_nodes() > 0:
            selected_id = st.selectbox("Select Paper", list(graph.nodes))
            if selected_id:
                display_names[selected_id] = st.text_input("Edit Title", value=display_names[selected_id])
                paper_info[selected_id]['author'] = st.text_input("Edit First Author", value=paper_info[selected_id]['author'])
                paper_info[selected_id]['pi'] = st.text_input("Edit PI", value=paper_info[selected_id].get('pi', 'Unknown'))
                paper_info[selected_id]['year'] = st.text_input("Edit Year", value=paper_info[selected_id]['year'])
                paper_links[selected_id] = st.text_input("Edit URL", value=paper_links[selected_id])
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Save Changes"):
                        save_graph_to_json(graph, display_names, paper_info, paper_links, DATA_FILE)
                        st.success("Changes saved")
                with col2:
                    if st.button("Delete Paper"):
                        graph.remove_node(selected_id)
                        display_names.pop(selected_id, None)
                        paper_info.pop(selected_id, None)
                        paper_links.pop(selected_id, None)
                        save_graph_to_json(graph, display_names, paper_info, paper_links, DATA_FILE)
                        st.success("Paper deleted")
                        st.rerun()
        else:
            st.info("No papers available to edit")

    # Graph Display Settings
    st.header("Graph Settings")
    layout_choice = st.radio("Layout", ["spring", "circular", "kamada-kawai", "random", "fruchterman-reingold"])
    color_mode = st.radio("Color Nodes By", ["First Author", "Principal Investigator", "Decade"])

# Main Graph Area
if graph.number_of_nodes() == 0:
    st.info("No papers in the graph. Add papers using the sidebar controls.")
else:
    fig = draw_graph_plotly(graph, display_names, paper_info, layout_choice, color_mode)
    
    # Display the plot
    st.plotly_chart(
        fig,
        use_container_width=True,
        height=800,
        key="graph"
    )

    # Add a button to clear selection
    if st.session_state.selected_node:
        if st.button("Clear Selection"):
            st.session_state.selected_node = None
            st.rerun()

    # Paper Library Table
    papers_data = []
    for paper_id in graph.nodes:
        papers_data.append({
            "DOI": paper_id,
            "Title": display_names.get(paper_id, "Unknown"),
            "1st Author": paper_info.get(paper_id, {}).get('author', "Unknown"),
            "PI": paper_info.get(paper_id, {}).get('pi', "Unknown"),
            "Year": paper_info.get(paper_id, {}).get('year', "Unknown"),
            "Link": paper_links.get(paper_id, "N/A")
        })

    if papers_data:
        df = pd.DataFrame(papers_data)
        # Create decade from Year column
        df["Decade"] = df["Year"].apply(lambda y: f"{(int(y)//10)*10}s" if str(y).isdigit() else "Unknown")
        
        # Display filters and table
        st.header("Paper Library")
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            title_filter = st.text_input("Filter by Title")
        with col2:
            author_filter = st.text_input("Filter by First Author")
        with col3:
            pi_filter = st.text_input("Filter by PI")
        with col4:
            year_filter = st.text_input("Filter by Year")
        with col5:
            decade_filter = st.text_input("Filter by Decade")

        # Apply filters
        filtered_df = df.copy()
        if title_filter:
            filtered_df = filtered_df[filtered_df['Title'].str.contains(title_filter, case=False, na=False)]
        if author_filter:
            filtered_df = filtered_df[filtered_df['1st Author'].str.contains(author_filter, case=False, na=False)]
        if pi_filter:
            filtered_df = filtered_df[filtered_df['PI'].str.contains(pi_filter, case=False, na=False)]
        if year_filter:
            filtered_df = filtered_df[filtered_df['Year'].str.contains(year_filter, case=False, na=False)]
        if decade_filter:
            filtered_df = filtered_df[filtered_df['Decade'].str.contains(decade_filter, case=False, na=False)]

        # Convert links to HTML
        filtered_df['Link'] = filtered_df['Link'].apply(
            lambda url: f'<a href="{url}" target="_blank">Link</a>' if isinstance(url, str) and url and url != "N/A" else ""
        )

        # Display table with both First Author and PI
        filtered_df = filtered_df[['DOI', 'Title', '1st Author', 'PI', 'Year', 'Decade', 'Link']]
        st.write(filtered_df.to_html(escape=False, index=False), unsafe_allow_html=True)

        # Citation Connections Section
        st.header("Citation Connections")
        selected_paper = st.selectbox("Select a paper to view its connections", list(graph.nodes()), format_func=lambda x: display_names[x])

        if selected_paper:
            # Get citing papers (papers that cite the selected paper)
            citing_papers = list(graph.predecessors(selected_paper))
            # Get cited papers (papers cited by the selected paper)
            cited_papers = list(graph.successors(selected_paper))

            # Create DataFrames for citing and cited papers
            citing_data = []
            for paper_id in citing_papers:
                citing_data.append({
                    "DOI": paper_id,
                    "Title": display_names.get(paper_id, "Unknown"),
                    "1st Author": paper_info.get(paper_id, {}).get('author', "Unknown"),
                    "PI": paper_info.get(paper_id, {}).get('pi', "Unknown"),
                    "Year": paper_info.get(paper_id, {}).get('year', "Unknown"),
                    "Link": paper_links.get(paper_id, "N/A")
                })

            cited_data = []
            for paper_id in cited_papers:
                cited_data.append({
                    "DOI": paper_id,
                    "Title": display_names.get(paper_id, "Unknown"),
                    "1st Author": paper_info.get(paper_id, {}).get('author', "Unknown"),
                    "PI": paper_info.get(paper_id, {}).get('pi', "Unknown"),
                    "Year": paper_info.get(paper_id, {}).get('year', "Unknown"),
                    "Link": paper_links.get(paper_id, "N/A")
                })

            # Display citation information
            st.subheader(f"Papers citing \"{display_names[selected_paper]}\"")
            if citing_data:
                citing_df = pd.DataFrame(citing_data)
                citing_df['Link'] = citing_df['Link'].apply(
                    lambda url: f'<a href="{url}" target="_blank">Link</a>' if isinstance(url, str) and url != "N/A" else ""
                )
                st.write(citing_df.to_html(escape=False, index=False), unsafe_allow_html=True)
            else:
                st.info("No papers cite this paper in the database")

            st.subheader(f"Papers cited by \"{display_names[selected_paper]}\"")
            if cited_data:
                cited_df = pd.DataFrame(cited_data)
                cited_df['Link'] = cited_df['Link'].apply(
                    lambda url: f'<a href="{url}" target="_blank">Link</a>' if isinstance(url, str) and url != "N/A" else ""
                )
                st.write(cited_df.to_html(escape=False, index=False), unsafe_allow_html=True)
            else:
                st.info("This paper doesn't cite any papers in the database")



