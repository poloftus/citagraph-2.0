# Citagraph 2.0

Citagraph is an interactive citation graph visualization tool built with Streamlit. It allows you to visualize and manage networks of academic papers and their citations.

## Features

- **Interactive Graph Visualization**: View citation relationships between papers using various graph layouts
- **Color Coding**: Visualize papers by author or decade
- **Dual User Modes**: Observer mode for viewing and Admin mode for editing
- **Paper Management**: Add, edit, and delete papers in the database
- **Citation Management**: Create and remove citation relationships between papers

## Installation

1. Clone this repository:
```bash
git clone https://github.com/YOUR-USERNAME/citagraph-2.0.git
cd citagraph-2.0
```

2. Install the required packages:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
streamlit run app.py
```

## Usage

### Observer Mode
- View the citation graph with different layouts
- Toggle between coloring by author or decade
- Browse the paper library

### Admin Mode
- Password-protected interface for data management
- Add new papers to the database
- Edit or delete existing papers
- Create or remove citation relationships between papers

## Default Admin Password
The default admin password is `admin123`. We recommend changing this in the `app.py` file for security purposes.

## Data Storage
Paper and citation data is stored in `data/citation_data2.json`.

## Screenshots

*[Add screenshots of your application here]*

## License

[Your chosen license]

## Contributing

1. Fork the project
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request
