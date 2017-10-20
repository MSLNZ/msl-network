"""
Common functions.
"""
import os


def ensure_root_path(path):
    """Ensure that the root directory of the file path exists.
        
    Parameters
    ----------
    path : :obj:`str`
        The file path.
        
        For example, if `path` is ``/the/path/to/my/test/file.txt`` then
        this function would ensure that the ``/the/path/to/my/test`` directory
        exists creating the intermediate directories if necessary.
    """
    root = os.path.dirname(path)
    if root and not os.path.isdir(root):
        os.makedirs(root)
