"""
Common functions.
"""
import os


def ensure_root_path(file_path):
    """Ensure that the root directory of the file path exists.
        
    Parameters
    ----------
    file_path : :obj:`str`
        The file path.
        
        For example, if `file_path` is ``path/to/my/test/file.txt`` then 
        this function would ensure that the ``path/to/my/test`` directory 
        exists creating the intermediate directories if necessary.
    """
    root = os.path.dirname(file_path)
    if not os.path.isdir(root):
        os.makedirs(root)
