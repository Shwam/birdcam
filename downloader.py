from html.parser import HTMLParser
import os.path
import requests
 
class SDParser(HTMLParser):
    links = []
    def handle_starttag(self, tag, attrs):
        if tag == "a":
            link = attrs[0][1]
            if link[:4] == "/sd/" and link[4] != ".":
                self.links.append(link)

class RecordParser(HTMLParser):
    links = []
    def handle_starttag(self, tag, attrs):
        if tag == "a":
            link = attrs[0][1]
            if link[-4:] == ".265":
                timestamp = link.split("/")[4].split(".")[0][1:]
                date, start, end = timestamp.split("_")
                if int(end) < 999999:
                    self.links.append((date + start, date + end, link))


 
def list_records(ip_address, creds):
    records = []
    request = f"http://{ip_address}/sd/"
    sd = (requests.get(request, auth=creds)._content.decode("utf8"))
    parser = SDParser()
    parser.feed(sd)
    for link in parser.links:
        date = link.split("/")[2]
        request = f"http://{ip_address}/sd/{date}/record000/"
        response = (requests.get(request, auth=creds)._content.decode("utf8"))
        record_parser = RecordParser()
        record_parser.feed(response)
        records.extend(record_parser.links)
    return records

def download(ip_address, creds, link):
    filename = "videos/" + link.split("/")[-1]
    if os.path.exists(filename):
        print(f"{filename} already exists, aborting")
        return True
    request = f"http://{ip_address}{link}"
    response = (requests.get(request, auth=creds)._content)
    with open(filename, "wb") as f:
        f.write(response)
    return True

def seek(start, end, records):
    start = start[2:]
    end = end[2:]
    urls = []
    found = False
    for record in records:
        l_start, l_end, l_url = record
        if not found:
            if start >= l_start and start <= l_end:
                urls.append(l_url)
                found = True
        else:
            if end >= l_end:
                urls.append(l_url)
            else:
                return urls

def clip(start, end, ip_address, creds):
    records = list_records(ip_address, creds)
    
    required_files = seek(start, end, records)
    for file in required_files:
        download(ip_address, creds, file)
    
if __name__ == "__main__":
    from auth import IP_ADDRESS, AUTH
    clip("20220516125300", "20220516125400", IP_ADDRESS, AUTH)
