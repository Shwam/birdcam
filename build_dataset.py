import os
import xml.etree.ElementTree as ET
import shutil

def darknet_label(image_dir, species=None):
    files = [filename[:-4] for filename in os.listdir(image_dir) if filename[-4:] == ".xml"]
    classes = ["bird"]
    counts = {}
    relevant_files = []

    for filename in files:
        try:
            tree = ET.parse(f"{image_dir}{filename}.xml")
        except Exception as err:
            print(filename, err)
            continue
        boxes = get_boxes(tree)
        unlabeled = True
        output = ""
        for box in boxes:
            x, y, w, h, label = box
            labelidx = 0
            if label == "bird":
                # this one hasn't been properly labeled yet
                unlabeled = True
                break
            if label in classes:
                labelidx = classes.index(label)
            elif not species or label in species:
                classes.append(label)
                labelidx = len(classes) - 1
            elif label not in species and "bird" in classes:
                labelidx = classes.index("bird") # label it as generic bird
            unlabeled = False
            output += f"{labelidx} {x} {y} {w} {h}"
            counts[classes[labelidx]] = counts.get(classes[labelidx], 0) + 1

        # save the file contents        
        if not unlabeled:
            with open(f"{image_dir}{filename}.txt", "w") as f:
                f.write(output)
            relevant_files.append(filename)

    for k in counts:
        print(k, counts[k])

    return relevant_files, classes 
 
def get_boxes(tree):            
    root = tree.getroot()
    
    size = root.find("size")
    width = int(size.find("width").text)
    height = int(size.find("height").text)
    
    boxes = []

    for obj in root.findall("object"):
        box = obj.find("bndbox")
        x1 = int(box.find("xmin").text)
        y1 = int(box.find("ymin").text)
        x2 = int(box.find("xmax").text)
        y2 = int(box.find("ymax").text)
        label = obj.find("name").text
        x = (x1+x2)/2/width
        y = (y1+y2)/2/width
        w = (x2-x1)/height
        h = (y2-y1)/height
        boxes.append((x,y,w,h,label))

    return boxes   

def make_config(num_classes):
    source_path = "darknet/cfg/yolov4-custom.cfg"
    config_path = "darknet/cfg/yolov4-bird.cfg"
    
    with open(source_path, 'r') as f:
        source = f.readlines()

    with open(config_path, 'w') as f:
        for i in range(len(source)):
            line = source[i]
            if "max_batches =" in line:
                max_batches=num_classes*2000
                f.write(f"max_batches={max_batches}\n")
            elif "steps=" in line:
                f.write(f"steps={int(max_batches*0.8)},{int(max_batches*0.9)}\n")
            elif "subdivisions=" in line:
                f.write("subdivisions=64\n")
            elif "width=" in line:
                f.write(f"width=608\n")
            elif "height=" in line:
                f.write(f"height=608\n")
            elif "classes=" in line:
                f.write(f"classes={num_classes}\n")
            elif "filters=255" in line:
                # scan ahead to the next tag
                j = i
                while j < len(source):
                    j+= 1
                    if source[j][0] == "[":
                        # only replace it if next tag is yolo
                        if "[yolo]" in source[j]:
                            f.write(f"filters={(num_classes+5)*3}\n")
                        else:
                            f.write(line)
                        break
            else:
                f.write(line)

     
if __name__ == "__main__":
    darknet_data = "darknet/data/"#"darknet/build/darknet/x64/data/"
    image_dir = "images/"
    # convert files to darknet format
    files, classes = darknet_label(image_dir, species=("mourning dove", "northern cardinal", "house finch"))
    # 1. Create config file
    make_config(len(classes))

    # 2. Create file obj.names
    with open(f"{darknet_data}obj.names", "w") as f:
        f.write("\n".join(classes))
    
    # 3. Create file obj.data
    with open(f"{darknet_data}obj.data", "w") as f:
        f.write(f"classes = {len(classes)}\ntrain  = data/train.txt\nvalid  = data/test.txt\nnames = data/obj.names\nbackup = backup/")

    # 4. Put image-files (.jpg) of your objects in the directory build\darknet\x64\data\obj
    if os.listdir(f"{darknet_data}obj/"):
        os.system(f"rm {darknet_data}obj/*")
    for filename in files:
        src = f"{image_dir}{filename}"
        dst = f"{darknet_data}obj/{filename}"
        #os.symlink(f"{src}.jpg",f"{dst}.jpg")
        shutil.copyfile(src+".jpg", dst+".jpg")
    # 5. Same for bounding box .txt files
        #os.symlink(f"{src}.txt",f"{dst}.txt")
        shutil.copyfile(src+".txt", dst+".txt")
    # 6. Creat train.txt
    darknet_files = [f"data/obj/{filename}.jpg" for filename in files]
    with open(f"{darknet_data}train.txt", "w") as f:
        f.write("\n".join(darknet_files))
    

