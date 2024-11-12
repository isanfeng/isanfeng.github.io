import os
import shutil

def move_all_and_overwrite(src_dir, dst_dir):
    # 确保源目录存在
    if not os.path.exists(src_dir):
        print(f"源目录 {src_dir} 不存在")
        return

    # 确保目标目录存在
    if not os.path.exists(dst_dir):
        os.makedirs(dst_dir)

    # 遍历源目录中的所有文件和子目录
    for item_name in os.listdir(src_dir):
        src_item = os.path.join(src_dir, item_name)
        dst_item = os.path.join(dst_dir, item_name)

        try:
            # 如果是文件，则直接移动（会覆盖同名文件）
            if os.path.isfile(src_item):
                if os.path.exists(dst_item):
                    os.remove(dst_item)
                shutil.move(src_item, dst_dir)
            # 如果是目录，且目标位置存在同名目录，则先删除目标目录再移动
            elif os.path.isdir(src_item):
                if os.path.exists(dst_item):
                    shutil.rmtree(dst_item)  # 删除目标位置的同名目录
                shutil.move(src_item, dst_dir)  # 移动源目录到目标位置
        except Exception as e:
            print(f"在移动 {src_item} 到 {dst_dir} 时出错: {e}")

src_dir = "./_site"  # 替换为你的源文件夹路径
dst_dir = "../isanfeng.github.io"  # 替换为你的目标文件夹路径
move_all_and_overwrite(src_dir, dst_dir)