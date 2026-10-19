import matplotlib.pyplot as plt
import numpy as np

# Crea un arreglo de x
x = np.linspace(-10, 10, 400)

# Crea un arreglo de y
y = np.sin(x)

# Plotea el grñfico
plt.plot(x, y)

# Muestra el grñfico
plt.show()
