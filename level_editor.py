# level_editor.py

import tkinter as tk
import json

GRID_SIZE = 50    # Grid size (number of visible tiles in each direction from 0,0)
TILE_SIZE = 20    # Size of each grid cell in pixels

# Define platform types and their colors
PLATFORM_TYPES = {
    'normal': 'green',
    'deadly': 'red',
    'gravity': 'blue',
    'erase': None  # Erase mode has no color
}

class LevelEditor:
    def __init__(self, master):
        self.master = master
        self.master.title("Level Editor")

        # Create a scrollable canvas
        self.canvas_frame = tk.Frame(master)
        self.canvas_frame.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(
            self.canvas_frame,
            width=800, height=600,
            scrollregion=(-GRID_SIZE*TILE_SIZE, -GRID_SIZE*TILE_SIZE, GRID_SIZE*TILE_SIZE, GRID_SIZE*TILE_SIZE)
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")

        # Scrollbars
        self.hbar = tk.Scrollbar(self.canvas_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.hbar.grid(row=1, column=0, sticky="we")

        self.vbar = tk.Scrollbar(self.canvas_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.vbar.grid(row=0, column=1, sticky="ns")

        self.canvas.config(xscrollcommand=self.hbar.set, yscrollcommand=self.vbar.set)

        # Bind trackpad scrolling
        self.canvas.bind("<MouseWheel>", self.scroll_vertical)  # Windows/macOS
        self.canvas.bind("<Shift-MouseWheel>", self.scroll_horizontal)  # Horizontal scrolling
        self.canvas.bind("<Button-4>", self.scroll_up)  # Linux scrolling up
        self.canvas.bind("<Button-5>", self.scroll_down)  # Linux scrolling down

        # State variables
        self.platform_type = tk.StringVar(value='normal')
        self.platform_data = {}
        self.start_tile = None  # For drag actions

        # UI for platform type selection
        self.create_platform_type_selector()

        # Mouse bindings
        self.canvas.bind("<Button-1>", self.start_drag)
        self.canvas.bind("<B1-Motion>", self.drag_action)
        self.canvas.bind("<ButtonRelease-1>", self.end_drag)
        self.canvas.bind("<Motion>", self.show_coordinates)

        # Display for mouse coordinates
        self.coord_label = tk.Label(master, text="Coordinates: (0, 0)")
        self.coord_label.pack()

        # Save button
        self.save_button = tk.Button(master, text="Save Level", command=self.save_level)
        self.save_button.pack()

        # Draw grid and highlight (0,0)
        self.draw_grid()

    def create_platform_type_selector(self):
        frame = tk.Frame(self.master)
        frame.pack()

        tk.Label(frame, text="Select Platform Type:").pack(side=tk.LEFT)
        for p_type, color in PLATFORM_TYPES.items():
            rb = tk.Radiobutton(frame, text=p_type.capitalize(), variable=self.platform_type, value=p_type)
            rb.pack(side=tk.LEFT)

    def draw_grid(self):
        # Draw grid lines and highlight the (0,0) cell
        for i in range(-GRID_SIZE, GRID_SIZE):
            self.canvas.create_line(i*TILE_SIZE, -GRID_SIZE*TILE_SIZE, i*TILE_SIZE, GRID_SIZE*TILE_SIZE, fill='lightgray')
        for j in range(-GRID_SIZE, GRID_SIZE):
            self.canvas.create_line(-GRID_SIZE*TILE_SIZE, j*TILE_SIZE, GRID_SIZE*TILE_SIZE, j*TILE_SIZE, fill='lightgray')

        # Highlight the (0,0) tile
        self.canvas.create_rectangle(
            0, 0, TILE_SIZE, TILE_SIZE,
            outline='black', width=2, fill='yellow', tags='origin'
        )

    def scroll_vertical(self, event):
        """Scroll vertically with the mouse wheel or trackpad."""
        self.canvas.yview_scroll(-1 * int(event.delta / 120), "units")

    def scroll_horizontal(self, event):
        """Scroll horizontally with shift + mouse wheel or trackpad."""
        self.canvas.xview_scroll(-1 * int(event.delta / 120), "units")

    def scroll_up(self, event):
        """Scroll up for Linux."""
        self.canvas.yview_scroll(-1, "units")

    def scroll_down(self, event):
        """Scroll down for Linux."""
        self.canvas.yview_scroll(1, "units")

    def start_drag(self, event):
        x, y = self.canvas_coords_to_grid(event.x, event.y)
        self.start_tile = (x, y)

    def drag_action(self, event):
        x, y = self.canvas_coords_to_grid(event.x, event.y)

        if self.start_tile:
            self.clear_preview()
            self.preview_platform(self.start_tile, (x, y))

    def end_drag(self, event):
        x, y = self.canvas_coords_to_grid(event.x, event.y)

        if self.start_tile:
            self.place_platform(self.start_tile, (x, y))
            self.start_tile = None

    def canvas_coords_to_grid(self, x, y):
        # Convert canvas pixel coordinates to grid coordinates
        grid_x = (self.canvas.canvasx(x) // TILE_SIZE)
        grid_y = (self.canvas.canvasy(y) // TILE_SIZE)
        return int(grid_x), int(grid_y)

    def clear_preview(self):
        self.canvas.delete('preview')

    def preview_platform(self, start_tile, end_tile):
        x1, y1 = start_tile
        x2, y2 = end_tile
        for x in range(min(x1, x2), max(x1, x2) + 1):
            for y in range(min(y1, y2), max(y1, y2) + 1):
                self.canvas.create_rectangle(
                    x * TILE_SIZE, y * TILE_SIZE, (x + 1) * TILE_SIZE, (y + 1) * TILE_SIZE,
                    fill=PLATFORM_TYPES.get(self.platform_type.get(), 'gray'), outline='black', tags='preview'
                )

    def place_platform(self, start_tile, end_tile):
        x1, y1 = start_tile
        x2, y2 = end_tile
        platform_type = self.platform_type.get()

        for x in range(min(x1, x2), max(x1, x2) + 1):
            for y in range(min(y1, y2), max(y1, y2) + 1):
                if platform_type == 'erase':
                    # Remove platform if it exists
                    if (x, y) in self.platform_data:
                        self.canvas.delete(self.platform_data[(x, y)]['rect'])
                        del self.platform_data[(x, y)]
                else:
                    # Place new platform
                    if (x, y) in self.platform_data:
                        self.canvas.delete(self.platform_data[(x, y)]['rect'])
                    rect = self.canvas.create_rectangle(
                        x * TILE_SIZE, y * TILE_SIZE, (x + 1) * TILE_SIZE, (y + 1) * TILE_SIZE,
                        fill=PLATFORM_TYPES[platform_type], outline='black'
                    )
                    self.platform_data[(x, y)] = {'type': platform_type, 'rect': rect}

    def show_coordinates(self, event):
        x, y = self.canvas_coords_to_grid(event.x, event.y)
        self.coord_label.config(text=f"Coordinates: ({x}, {y})")

    def save_level(self):
        platform_configs = []
        for (x, y), data in self.platform_data.items():
            config = {
                "grid_x": x,
                "grid_y": y,
                "width_in_tiles": 1,
                "height_in_tiles": 1,
                "platform_type": data['type']
            }
            platform_configs.append(config)

        with open('level_data.json', 'w') as f:
            json.dump(platform_configs, f, indent=4)

        tk.messagebox.showinfo("Level Saved", "Level data has been saved to 'level_data.json'.")

if __name__ == '__main__':
    root = tk.Tk()
    app = LevelEditor(root)
    root.mainloop()
