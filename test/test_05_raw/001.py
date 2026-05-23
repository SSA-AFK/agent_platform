import os
from pathlib import Path


#拿取文件名
# file_path = os.path.basename(__file__).split( ".")[0]
file_path = Path(__file__).stem

#拿取文件后缀
file_end = Path(__file__).suffix

print(file_path)

print(file_end)


