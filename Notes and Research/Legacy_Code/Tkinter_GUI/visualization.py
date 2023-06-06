# GUI Version 1, visualization.py uses tkinter and matplotlib to generate the asset's path as data is received from the message broker. This attempt did not render fast enough upon testing with live data, with a bottleneck developing as the line artist is drawn, even after implementing several optimization strategies.

import tkinter as tk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import paho.mqtt.client as mqtt
import json
from tkinter import scrolledtext
import matplotlib.image as mpimg
from app.lib.message_handler import Handler
from timeit import default_timer as timer
import math
from PIL import Image, ImageTk
from tkinter import ttk as tkk
from collections import deque
import numpy as np
import paho.mqtt.publish as publish
from paho.mqtt.client import MQTTv5

class PlotterGUI(tk.Tk):
    def __init__(self, broker_host, topic_sub, port):
        super().__init__()

        self.title("Plotter")
        self.counter = 0
        self.last_heading = 0

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # Define the length of the queue
        self.queue_length = 100

    # Create a deque for x and y values
        self.x_queue = deque(maxlen=self.queue_length)
        self.y_queue = deque(maxlen=self.queue_length)

    # Domain and range of graph
        self.min_x = -8000
        self.max_x = 8000
        self.min_y = -4000
        self.max_y = 4000

        self.span_x = abs(self.min_x)+abs(self.max_x)
        self.span_y = abs(self.min_y)+abs(self.max_y)
        self.denominator = math.gcd(self.span_x, self.span_y)

    # Create Figure
        self.fig = Figure(figsize=(self.span_x/self.denominator, self.span_y/self.denominator), dpi=100)
        self.ax = self.fig.add_subplot(111, xlim=[self.min_x, self.max_x], ylim=[self.min_y, self.max_y])
        self.ax.set_xlabel("X (mm)")
        self.ax.set_ylabel("Y (mm)")
        self.font = {'family':'serif', 'color':'black','size':22, 'weight':'bold'}
        self.ax.set_title("CS.23.322 - Real Time Indoor Wheel Based Asset Localization System", fontdict=self.font, y=1.05)
        for axis in ['top', 'bottom', 'left', 'right']:
            self.ax.spines[axis].set_linewidth(3)       # change width
            self.ax.spines[axis].set_color('#FFCE00')    # change color

    # Create artist object for adding select points to plot
        self.line, = self.ax.plot([], [], 'bo-')

    # Import background image
        self.map_img = mpimg.imread('app/Visualization/Assets/map_01.png')

    # Set background image size to cover graph dimentions
        self.ax.imshow(self.map_img, extent=[self.min_x, self.max_x, self.min_y, self.max_y], aspect='auto')

    # Set domain and range of graph
        self.ax.set_xlim([self.min_x, self.max_x])
        self.ax.set_ylim([self.min_y, self.max_y])

    # create the graph frame
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(side=tk.LEFT, fill=tk.BOTH, expand=1)

    # Background color
        self.fig.patch.set_facecolor('#FFB300')

    # Reset button widget
        self.reset_button = tk.Button(master=self, text="Reset", command=self.reset)
        self.reset_button.pack(side=tk.BOTTOM, pady=10)

    # Create sidebar
        # s = tkk.Style()
        # s.configure('test.TFrame', background='black')
        # self.sidebar = tkk.Frame(self, style='test.TFrame')
        self.sidebar = tk.Frame(self)
        self.sidebar.pack(side=tk.RIGHT, fill=tk.Y, padx=10, pady=10, ipady=20, expand=False)

    # Create image label
        self.image_label = tk.Label(self.sidebar, bg="black")
        self.image_label.pack(side=tk.TOP, fill=tk.X)

    # Load image and resize it to a specific width
        self.vcu_img = Image.open("app/Visualization/Assets/VCU_engineering.png")
        self.max_width = 260

    # Calculate the height while maintaining the aspect ratio
        self.w, self.h = self.vcu_img.size
        aspect_ratio = self.h / self.w
        self.height = int(aspect_ratio * self.max_width)

    # Resize TODO replace deprecated ANTIALIAS with something else
        self.vcu_img = self.vcu_img.resize((self.max_width, self.height), Image.ANTIALIAS)

    # Convert the image to a Tkinter PhotoImage
        self.photo = ImageTk.PhotoImage(self.vcu_img)
        self.image_label.config(image=self.photo)

    # Create label for heading text
        self.curr_heading = tk.StringVar()
        self.curr_heading.set("Heading: ---")
        # self.heading_label = tk.Label(self.sidebar, text=self.curr_heading.get(), font={"Roboto", 8})
        self.heading_label = tk.Label(self.sidebar, text=self.curr_heading.get())
        self.heading_label.pack(side=tk.BOTTOM)

    # Create compass frame
        self.heading_canvas = tk.Canvas(self.sidebar, bg="#F0F0F0")
        self.heading_canvas.config(width=150, height=150)
        self.heading_canvas.pack(side=tk.BOTTOM, fill=tk.NONE, expand=False)

    # Create compass icon
        self.radius = 50
        self.canvas_middle = [int(self.heading_canvas['width'])/2, int(self.heading_canvas['height'])/2] 
        self.heading_canvas.update()
        self.heading_canvas.create_oval(25, 25, 125, 125, fill='#FFB300', outline='#FFCE00', width=5)
        self.triangle_id = self.heading_canvas.create_polygon(self.canvas_middle[0], self.canvas_middle[1] - 30, self.canvas_middle[0] - 20, self.canvas_middle[1] + 25, self.canvas_middle[0], self.canvas_middle[1] + 15, self.canvas_middle[0] + 20, self.canvas_middle[1] + 25, fill='#333333')

    # Create scrolling text box for coordinates
        self.listbox = scrolledtext.ScrolledText(self.sidebar, wrap=tk.WORD, height=0, width="30", relief="flat", borderwidth=5, padx=5, pady=5, foreground="#333333")
        self.listbox.pack(side=tk.TOP, fill=tk.Y, expand=1)
        self.listbox.insert(tk.END, "X (mm), Y (mm)\n")

    # Set up MQTT client
        self.handler = Handler(client_id='gui', topic_sub=topic_sub, host=broker_host, port=port, qos=0)
        self.handler.client.message_callback_add(topic_sub, self.on_message)
        self.handler.connect()
        self.handler.client.loop_start()

    def rotate_triangle(self, canvas, triangle_id, radians):
        # Get the current coords of vertices
        coords = np.array(canvas.coords(triangle_id))
        # Reshape coords into a 3x2 array of vertices
        vertices = coords.reshape((4, 2))        
        # Calculate the sine and cosine of the angle
        cosine = np.cos(radians)
        sine = np.sin(radians)        
        # Shift vertices to the origin
        origin_vertices = vertices - self.canvas_middle
        # Rotate vertices about the origin
        rotated_vertices = np.dot(origin_vertices, np.array([[cosine, sine], [-sine, cosine]]))
        # Shift vertices back to original positions
        new_vertices = rotated_vertices + self.canvas_middle        
        # Flatten the array and update the triangle's coordinates on the canvas
        flat_coords = new_vertices.ravel().tolist()
        canvas.coords(triangle_id, *flat_coords)

    def update_image_extent(self):
        self.ax.images.pop()
        self.ax.imshow(self.img, extent=[self.min_x, self.max_x, self.min_y, self.max_y], aspect='auto')
        
    def on_message(self, client, userdata, msg):
        mod = 5
        if self.counter % mod == 0:  
            data = json.loads(msg.payload)

            if "heading" in data:
                heading = data["heading"]
                rotation = self.last_heading - heading
                self.rotate_triangle(self.heading_canvas, self.triangle_id, rotation)
                self.curr_heading.set("Heading: {:.2f}\u00B0".format(math.degrees(heading)))
                self.heading_label.config(text=self.curr_heading.get())
                self.last_heading = heading
            if "x_loc" in data and "y_loc" in data:
                x = data["x_loc"]
                y = data["y_loc"]

                # Insert X,Y into the scrolling textbox
                self.listbox.insert(tk.END, f"{x:.6f}, {y:.6f}\n")
                # Delete first line from scrolling textbox once 100 items are logged
                if self.counter > 100*mod:
                    self.listbox.delete("1.0", "2.0")
                self.listbox.see(tk.END)
                # Add Coords to queues
                self.x_queue.append(x)
                self.y_queue.append(y)
                # Update line based on new queue

                self.start = timer()
                self.line.set_data(self.x_queue, self.y_queue)

                # Redrawy the line
                self.ax.draw_artist(self.line)
                # Update the altered Figure
                self.fig.canvas.draw_idle()
                self.current_time = timer() 
        self.counter +=1 

    def on_close(self):
        self.handler.client.disconnect()
        self.handler.client.loop_stop()
        self.destroy()

    def reset(self):
        publish.single(
            topic="Debug/info",
            payload=json.dumps({"reset": True}),
            hostname=broker_host,
            qos=1,
            protocol=MQTTv5
            )

if __name__ == '__main__':
    broker_host = "10.53.250.5"
    topic_sub = "Data/location"
    gui = PlotterGUI(broker_host, topic_sub, 1883)
    # gui.attributes('-fullscreen', True)
    gui.mainloop()
