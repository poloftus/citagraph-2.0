import json
import os
import itertools
import pandas as pd
import networkx as nx
import plotly.graph_objects as go
import streamlit as st

DATA_FILE = 'citation_data3.json'
ADMIN_PASSWORD = "admin123"  # Set your admin password here

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
        color_map = {
            1980: 'rgb(255, 99, 71)',
            1990: 'rgb(34, 139, 34)',
            2000: 'rgb(30, 144, 255)',
            2010: 'rgb(255, 215, 0)'
        }
        return color_map.get(decade, 'rgb(211, 211, 211)')
    except:
        return 'rgb(211, 211, 211)'

def get_author_color(author, color_map):
    if author in color_map:
        return color_map[author]
    color = next(author_color_cycle)
    color_map[author] = color
    return color

def display_paper_table(paper_data):
    df = pd.DataFrame(paper_data).copy()

    # Ensure required columns exist
    for col in ['id', 'title', 'author', 'year', 'decade', 'link']:
        if col not in df.columns:
            df[col] = ""

    # Safely convert links to HTML
    df['link'] = df['link'].apply(lambda url: f'<a href="{url}" target="_blank">Link</a>' if isinstance(url, str) and url and url != "N/A" else "")

    df = df[['id', 'title', 'author', 'year', 'decade', 'link']]
    st.markdown("### 📚 Paper Library")
    st.write(df.to_html(escape=False, index=False), unsafe_allow_html=True)


def filter_papers(df):
    st.sidebar.markdown("### 🔍 Filter Papers")

    # Define filterable fields and their input types
    filters = {
        "title": st.sidebar.text_input("Search by Title"),
        "author": st.sidebar.text_input("Search by Author"),
        "year": st.sidebar.text_input("Search by Year"),
        "decade": st.sidebar.text_input("Search by Decade"),
    }

    # Apply filters dynamically
    filtered_df = df.copy()
    for field, query in filters.items():
        if query:
            filtered_df = filtered_df[filtered_df[field].astype(str).str.contains(query, case=False, na=False)]

    return filtered_df



# ----------------- Graph Plotting -------------------
def draw_graph_plotly(graph, display_names, paper_info, layout_choice, color_mode):
    # Define author color cycle
    global author_color_cycle
    author_color_cycle = itertools.cycle([ 
        'rgb(255, 99, 71)', 'rgb(34, 139, 34)', 'rgb(30, 144, 255)', 
        'rgb(255, 215, 0)', 'rgb(255, 105, 180)', 'rgb(75, 0, 130)', 
        'rgb(255, 69, 0)', 'rgb(0, 128, 128)', 'rgb(138, 43, 226)', 
        'rgb(255, 140, 0)'
    ])

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

    if color_mode == "author":
        if 'author_colors' not in st.session_state:
            st.session_state.author_colors = {}
        color_map = st.session_state.author_colors
    elif color_mode == "decade":
        if 'decade_colors' not in st.session_state:
            st.session_state.decade_colors = {}
        color_map = st.session_state.decade_colors

    # Assign colors to nodes based on author or decade
    for node in graph.nodes():
        author = paper_info.get(node, {}).get('author', 'Unknown')
        year = paper_info.get(node, {}).get('year', 'Unknown')
        label = author if color_mode == "author" else f"{(int(year)//10)*10}s" if str(year).isdigit() else "Unknown"

        if color_mode == "decade":
            color = get_decade_color(year)
        else:
            color = get_author_color(author, color_map)

        if label not in color_groups:
            color_groups[label] = {'x': [], 'y': [], 'text': [], 'color': color}

        x, y = pos[node]
        title = display_names.get(node, node)
        text = f"{title}<br>{author} ({year})<br><b>Paper ID:</b> {node}"
        color_groups[label]['x'].append(x)
        color_groups[label]['y'].append(y)
        color_groups[label]['text'].append(text)

    # Create edges
    edge_x, edge_y = [], []
    for src, dst in graph.edges():
        x0, y0 = pos[src]
        x1, y1 = pos[dst]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])

    edge_trace = go.Scatter(
        x=edge_x, y=edge_y,
        line=dict(width=1, color='#888'),
        hoverinfo='none',
        mode='lines',
        showlegend=False
    )

    node_traces = []
    for label, group in color_groups.items():
        node_traces.append(go.Scatter(
            x=group['x'], y=group['y'],
            mode='markers',
            hoverinfo='text',
            text=group['text'],
            marker=dict(
                color=group['color'],
                size=12,
                line=dict(width=2, color='DarkSlateGrey')
            ),
            name=label
        ))

    fig = go.Figure(data=[edge_trace] + node_traces)

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
        )
    )

    return fig

# ----------------- Streamlit UI -------------------
st.set_page_config(layout='wide')
st.title("Citagraph 3.0")

# Ask for password only if admin mode is selected
viewer_option = st.sidebar.radio("Proceed as Viewer", ["Observer Mode", "Admin Mode"])

if viewer_option == "Admin Mode":
    # Display password box only when Admin Mode is selected
    password = st.text_input("Enter Admin Password:", type="password")
    if password == ADMIN_PASSWORD:
        is_admin = True
        st.sidebar.success("You are now in Admin Mode.")
    else:
        is_admin = False
        if password:
            st.sidebar.error("Invalid password. Please try again.")
else:
    is_admin = False
    st.sidebar.success("Observer Mode.")

# Load Graph Data
graph, display_names, paper_info, paper_links = load_graph_from_json(DATA_FILE)

# Sidebar: Admin Controls (Visible only in Admin Mode)
if is_admin:
    with st.sidebar.expander("Add New Paper"):
        new_id_input = st.text_input("Paper ID (leave blank to auto-assign)")
        new_title = st.text_input("Title")
        new_author = st.text_input("Author")
        new_year = st.text_input("Year")
        new_url = st.text_input("URL")

        if st.button("Add Paper"):
            # Auto-generate Paper ID if no ID is provided
            if new_id_input.strip() == "":
                # Find the next available numeric ID by checking existing papers and assigning a formatted ID
                existing_ids = {str(id) for id in graph.nodes}
                i = 1
                while f"{i:04d}" in existing_ids:  # Use 4-digit format with leading zeros
                    i += 1
                new_id = f"{i:04d}"  # Generate the ID in the same format as existing ones
            else:
                new_id = new_id_input.strip()

            # Now add the paper with the appropriate ID
            graph.add_node(new_id)
            display_names[new_id] = new_title
            paper_info[new_id] = {'author': new_author, 'year': new_year}
            paper_links[new_id] = new_url
            save_graph_to_json(graph, display_names, paper_info, paper_links, DATA_FILE)
            st.success(f"Added paper '{new_title}' with ID {new_id}")





    with st.sidebar.expander("Edit/Delete Paper"):
        selected_id = st.selectbox("Select Paper to Edit/Delete", list(graph.nodes))
        if selected_id:
            display_names[selected_id] = st.text_input("Edit Title", value=display_names[selected_id])
            paper_info[selected_id]['author'] = st.text_input("Edit Author", value=paper_info[selected_id]['author'])
            paper_info[selected_id]['year'] = st.text_input("Edit Year", value=paper_info[selected_id]['year'])
            paper_links[selected_id] = st.text_input("Edit URL", value=paper_links[selected_id])
            if st.button("Save Changes"):
                save_graph_to_json(graph, display_names, paper_info, paper_links, DATA_FILE)
                st.success("Changes saved")
            if st.button("Delete Paper"):
                graph.remove_node(selected_id)
                display_names.pop(selected_id, None)
                paper_info.pop(selected_id, None)
                paper_links.pop(selected_id, None)
                save_graph_to_json(graph, display_names, paper_info, paper_links, DATA_FILE)
                st.success("Paper deleted")

    with st.sidebar.expander("Edit Citations"):
        source_paper = st.selectbox("Select Source Paper", list(graph.nodes))
        target_paper = st.selectbox("Select Target Paper", list(graph.nodes))
        if st.button("Add Citation"):
            if not graph.has_edge(source_paper, target_paper):
                graph.add_edge(source_paper, target_paper)
                save_graph_to_json(graph, display_names, paper_info, paper_links, DATA_FILE)
                st.success(f"Added citation from {source_paper} to {target_paper}")
            else:
                st.warning(f"Citation already exists from {source_paper} to {target_paper}")
        if st.button("Remove Citation"):
            if graph.has_edge(source_paper, target_paper):
                graph.remove_edge(source_paper, target_paper)
                save_graph_to_json(graph, display_names, paper_info, paper_links, DATA_FILE)
                st.success(f"Removed citation from {source_paper} to {target_paper}")
            else:
                st.warning(f"No citation exists from {source_paper} to {target_paper}")

# Sidebar: Graph Display Settings (Visible for both Admin and Viewer)
with st.sidebar.expander("Graph Display Settings", expanded=True):
    layout_choice = st.radio("Layout", ["spring", "circular", "kamada-kawai", "random", "fruchterman-reingold"])
    color_mode = st.radio("Color Nodes By", ["author", "decade"])

# Main Graph
if graph.number_of_nodes() == 0:
    st.warning("No data in graph. Add papers using the sidebar.")
else:
    fig = draw_graph_plotly(graph, display_names, paper_info, layout_choice, color_mode)
    st.plotly_chart(fig, use_container_width=True, height=800, config={'displayModeBar': False})

# ----------------- Show Paper Information -------------------
st.subheader("Paper Library")

# Create a DataFrame for papers
papers_data = []
for paper_id in graph.nodes:
    papers_data.append({
        "id": paper_id,
        "title": display_names.get(paper_id, "Unknown"),
        "author": paper_info.get(paper_id, {}).get('author', "Unknown"),
        "year": paper_info.get(paper_id, {}).get('year', "Unknown"),
        "link": paper_links.get(paper_id, "N/A")
    })

if papers_data:
    df = pd.DataFrame(papers_data)
    df["decade"] = df["year"].apply(lambda y: f"{(int(y)//10)*10}s" if str(y).isdigit() else "Unknown")

    # Apply sidebar filters
    filtered_df = filter_papers(df)

    # Show table
    display_paper_table(filtered_df.to_dict(orient='records'))
else:
    st.write("No papers available.")



