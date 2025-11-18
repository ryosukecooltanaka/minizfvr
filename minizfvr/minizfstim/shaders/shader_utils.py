from pathlib import Path

def get_in_package_shader_path(shader_name):
    """
    If you use scene_engine to render your stimulus using OpenGL,
    you need to give the glsl source code to the SceneEngine so that it can create shaders.
    The minizfvr package itself contains some glsl shaders. This utility function will
    return paths to those built-in shader files.
    """
    shader_parent_dir = Path(__file__).resolve().parent
    specified_shader_dir = shader_parent_dir / shader_name

    if not specified_shader_dir.exists():
        raise FileNotFoundError("No built-in shader named "+shader_name)

    return str(specified_shader_dir)
    

