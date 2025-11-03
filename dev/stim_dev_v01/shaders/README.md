# Note on Vertex shader and projection matrices

In the modern OpenGL pipeline, you are expected to write your own vertex shaders (as opposed to using the old school utility functions such as glLookat etc.).

Because I keep forgetting how exactly these things work and become incapable of reading the shader code I wrote myself, I am leaving a note here for future self.

There are three transformations to be taken care of, which are
- **Model transformation** (from local coordinates of the object to the world coordinate)
- **Viewing transformation** (from the world coordinate to the camera-centered view coordinate)
- **Perspective projection** (from the view coordinate to the normalized device coordinate)

Because the model transformation is somewhat trivial (it is just vanila translation/rotation/scaling), my focus will be on the **viewing transformation** and **perspective projection**.

For writing this, I primarily relied on Japanese sources (like notes by game devs) which I found more useful than course slides in random US colleges (which is what shows up if you google these topics in English).

**Source materials:**
[Qiita article by @ryutorin](https://qiita.com/ryutorion/items/0824a8d6f27564e850c9) /
[CS lecture note from U Tsukuba by Prof. Kanamori](https://kanamori.cs.tsukuba.ac.jp/lecture/old2017/cg_basics/03/03_slides.pdf) /
[LearnOpenGL](https://learnopengl.com/Getting-started/Coordinate-Systems)

## Notations and conventions

Here, I will stick to vertical vectors like 
```math
\mathbf{v} = \begin{bmatrix}
x \\
y \\
z \\
1
\end{bmatrix} = \begin{bmatrix} x & y & z & 1 \end{bmatrix}^T
```
and write transformations as left multiplication like 
```math
A = \begin{bmatrix}
a & b\\
c & d \end{bmatrix},\quad
\mathbf{v} = \begin{bmatrix} x \\ y \end{bmatrix},\quad
A\mathbf{v} = \begin{bmatrix}
ax + by \\
cx + dy \end{bmatrix}.
```
I am making this explicit because people use different conventions.

Note that, [in GLSL, matrix definitions are *column-first*](https://thebookofshaders.com/glossary/?search=mat4). 
That is, for example, the matrix below
```
mat3(
  a, b, c,
  d, e, f,
  g, h, i
);
```
means
```math
\begin{bmatrix}
a & d & g\\
b & e & h\\
c & f & i\end{bmatrix}.
```
So what you see visually is a transpose of the actual matrix!

Also note that OpenGL use the right-handed coordinate (for a historical reason; because shaders are programmable, you are actually free to do whatever you like) whereas the 'Normalized Device Coordinate' (NDC) is left-handed.
As a consequence, the perspective projection involves flipping of Z axis (OpenGL thinks negative Z is far, whereas NDC thinkg positive Z is far).

## Viewing transformation

A viewing transformation moves a vertex in the world coordinate to the camera-centered, view coordinate.

First of all, because the viewing transformation obviously involves translating points, it cannot be represented as a linear transformation in the 3D (equivalently, it cannot be expressed by 3 x 3 matrix multiplication).

Instead, we use a trick called *homogeneous notation*: We think of a line in 4D space, and consider every point on this line
$`\begin{bmatrix}wx & wy & wz & w\end{bmatrix}^T`$ (where $`w\neq0`$ being the free parameter) to be representing the same point in 3D
$`\begin{bmatrix}x & y & z \end{bmatrix}^T`$. Once we use this expanded notation, we can express translation with a matrix multiplication, such that

```math
\begin{bmatrix}
1 & 0 & 0 & a\\
0 & 1 & 0 & b\\
0 & 0 & 1 & c\\
0 & 0 & 0 & 1
\end{bmatrix}
\begin{bmatrix}
x \\ y \\ z \\ 1
\end{bmatrix} =
\begin{bmatrix}
x+a \\ y+b \\ z+c \\ 1
\end{bmatrix}.
```

Now, let us assume that 
- the coordinate of our vertex is $`\mathbf{P}=\begin{bmatrix}P_x & P_y & P_z\end{bmatrix}^T`$, 
- the position of our camera is $`\mathbf{C}=\begin{bmatrix}C_x & C_y & C_z\end{bmatrix}^T`$,
- the point we are looking at (gaze) is $`\mathbf{G}`$, and
- the vector indicating up is  $`\mathbf{U}`$.

First, the line of sight in the view coordinate will point negative Z (as per OpenGL's right-handed convention). 
Thus we define the new Z axis as a unit vector $`\mathbf{Z^*}=-\dfrac{(\mathbf{G}-\mathbf{C})}{\left|\mathbf{G}-\mathbf{C}\right|}`$ (negative of gazing point minus camera).

Now, given the up vector $`\mathbf{U}`$, the new X (side) axis can be derived as a cross product: 
$`\mathbf{X^*}=\dfrac{\mathbf{U}\times\mathbf{Z^*}}{\left|\mathbf{U}\times\mathbf{Z^*}\right|}`$ (Cross product follows the right-hand rule, so Y-Z order results in properly right-handed X).

Because $`\mathbf{U}`$ is not guaranteed to be orthogonal to  $`\mathbf{Z^*}`$, we recalculate the new Y axis as
$`\mathbf{Y^*}=\mathbf{Z^*}\times\mathbf{X^*}`$ (again note the order). Now we have an orthonormal bases for the view coordinate.

The vertex position in the view coordinate $`\mathbf{P^*}`$ can be obtained by subtracting the camera position from the vertex position (in the world coordinate) and projecting it onto the three new axes. 
That is:
```math
\mathbf{P^*} = \begin{bmatrix}
  \mathbf{X^*} \cdot (\mathbf{P}-\mathbf{C}) \\
  \mathbf{Y^*} \cdot (\mathbf{P}-\mathbf{C}) \\
  \mathbf{Z^*} \cdot (\mathbf{P}-\mathbf{C})
\end{bmatrix}
=
\begin{bmatrix}
  \mathbf{X^*} \cdot \mathbf{P} - \mathbf{X^*} \cdot \mathbf{C} \\
  \mathbf{Y^*} \cdot \mathbf{P} - \mathbf{Y^*} \cdot \mathbf{C} \\
  \mathbf{Z^*} \cdot \mathbf{P} - \mathbf{Z^*} \cdot \mathbf{C}
\end{bmatrix}.
```
The first term is simply a product between the vertex position and the new axes, and the second term represents the translation. 
Using the homogeneous notation to express the translational term, we can finaly write the viewing transform as a following 4 x 4 matrix:
```math
\begin{bmatrix} \mathbf{P^*} \\ 1 \end{bmatrix} =
\begin{bmatrix}
  & {\mathbf{X^*}^T} & & -\mathbf{X^*} \cdot \mathbf{C} \\
  & {\mathbf{Y^*}^T} & & -\mathbf{Y^*} \cdot \mathbf{C} \\
  & {\mathbf{Z^*}^T} & & -\mathbf{Z^*} \cdot \mathbf{C} \\
  0 & 0 & 0 & 1
\end{bmatrix}
\begin{bmatrix} \mathbf{P} \\ 1 \end{bmatrix}
```







