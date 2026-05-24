from flask import Flask, send_from_directory, send_file, current_app
from pathlib import Path
import os
import util

app = Flask(__name__)

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]

STYLE = """<style>img {
  max-width: 100%;
  height: auto;
}
a {
    font-size: 50px;
}
</style>"""

def dir_to_html(directory):
    html = STYLE
    if directory[-4:].lower() in (".jpg", ".ico"):
        # Just serve the image
        return send_file(Path(current_app.config["ROOT_DIR"])/directory, mimetype='image/png')

    full_path = os.path.join(current_app.config["ROOT_DIR"], directory)
    for fname in sorted(os.listdir(full_path)):
        path = Path(os.path.join(full_path, fname))
        if path.is_dir():
            link_text = fname
            if len(directory.split("/")) == 1:
                link_text = "20" + fname
            elif len(directory.split("/")) == 2:
                link_text = MONTHS[int(fname)] 
            html += f'<a href="{fname}/">{link_text}</a>\n'
        elif path.is_file() and fname[-4:].lower() == ".jpg":
            # Display images directly
            html += f"""
    <a href="{fname}">
        <img src="{fname}" alt="Description of image">
    </a>"""

    return html

@app.route('/')
@app.route('/<path:filename>')
def serve_file(filename=''):
    requested_path = (Path(current_app.config["ROOT_DIR"])/filename).resolve()
    if not str(requested_path).startswith(current_app.config["ROOT_DIR"]):
        return 404
    return dir_to_html(filename)

def serve_images(config):
    app.config['ROOT_DIR'] = os.path.abspath(config.get("output_dir", "images"))
    PORT = config.get("fileserver_port", 8080)
    app.run(debug=True, host="0.0.0.0", port=PORT)

if __name__ == '__main__':
    serve_images(util.load_config(".config"))
