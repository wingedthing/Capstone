import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import pandas as pd

def animation(i):
  data = pd.read_csv('data_to_plot.csv')
  x = []
  y = []
  x = data[0:i]['x']
  y = data[0:i]['y']  
  ax.clear()
  ax.set_ylim((-400,300))
  ax.set_xlim((-700,700))
  ax.plot(x, y)

plt.style.use('seaborn')
fig = plt.figure()
ax = fig.add_subplot(1,1,1)
animation = FuncAnimation(fig, func=animation, interval=250)
plt.show()