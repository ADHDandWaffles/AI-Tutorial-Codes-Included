import os

def map_directory(start_path, output_file="folder_structure.txt"):
    with open(output_file, 'w', encoding='utf-8') as f:
        for root, dirs, files in os.walk(start_path):
            level = root.replace(start_path, '').count(os.sep)
            indent = ' ' * 4 * level
            f.write(f"{indent}{os.path.basename(root)}/\n")
            subindent = ' ' * 4 * (level + 1)
            for file in files:
                f.write(f"{subindent}{file}\n")

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    map_directory(base_dir)
    print("Folder structure saved to 'folder_structure.txt'")
