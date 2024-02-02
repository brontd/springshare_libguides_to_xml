from mailer import Mailer
import paramiko, os
import time
# import smtplib
from datetime import datetime
import requests, json
from pprint import pprint
import configparser
import re

# To test locally... 
# docker-compose up
# docker exec -it python_springshare_api /bin/sh

# Process
#  1. Acquire token
#  2. Access API and return JSON
#  3. Iterate JSON, transform into XML, save to /home/ddavi7/springshare_libguides_to_xml/code/libguides/
#  4. SFTP XML file to sftp_host = 'libilssupport01.uky.edu' --> '/ftproot/alma/depot/LibGuides/
#  5. Email results...

# login
# https://uky.libapps.com/libapps/login.php?target64=L2xpYmd1aWRlcy9hcGkucGhw

base_url = 'https://lgapi-us.libapps.com/1.2/'
base_token_url = 'https://lgapi-us.libapps.com/1.2/oauth/token'

def acquire_token():
    headers = {'client_id':'680','client_secret':'e5cb884b62605bea68c1e8575434823b','grant_type':'client_credentials'}
    token_request = requests.post(base_token_url, data=headers)
    token_json = token_request.json()
    
    try:
        token = token_json['access_token']
        
    except:
        token = 'error'

    return token    

def access_endpoint(token, endpoint):
    bearer = 'Bearer ' + token
    auth = {'Authorization': bearer}
    url = base_url + endpoint['path'] + endpoint['expansion']
    data = requests.get(url, headers=auth)
    data.close
    json = data.json()

    return json

def iterate_json(endpoint, json_data, local_directory, today):
    
    counter = 1
    json_results = '\r\nJSON\r\\n'
    
    try:
        xml = '<' + endpoint['path'] +'>\n'
        for item in json_data:
            counter += 1

            # Added topic guides per management... bd
            # type_id == 3... topic guide
            # type_id == 4... subject guide
            if item['type_id'] == 3 or item['type_id'] == 4:    
                
                # common fields
                xml += '<item>\n'
                xml += '\t<id>'+str(item['id'])+'</id>\n'
                # xml += '\t<name>'+item['name']+'</name>\n'
                # xml += '\t<description>'+item['description']+'</description>\n'
                
                # Request per Jason Griffiths... some names/descriptions are coming through with &'s that cause XML load into ALMA to fail. &amp; works... so, regex substitution... bd 
                name_xml = '\t<name>'+item['name']+'</name>\n'
                name_corrected = re.sub("& ", "&amp; ", name_xml)                
                xml += name_corrected

                description_xml = '\t<description>'+item['description']+'</description>\n'
                description_corrected = re.sub("& ", "&amp; ", description_xml)                
                xml += description_corrected

                # guides fields
                if endpoint['path'] == 'guides':
                    if item['owner_id']:
                        xml += '\t<owner_id>'+str(item['owner_id'])+'</owner_id>\n'
                    xml += '\t<updated>'+item['updated']+'</updated>\n'
                    xml += '\t<status_label>'+item['status_label']+'</status_label>\n'
                    xml += '\t<type_label>'+item['type_label']+'</type_label>\n'
                    xml += '\t<friendly_url>'+item['friendly_url']+'</friendly_url>\n'
                    xml += '\t<url>'+item['url']+'</url>\n'
                    if item['owner']:
                        owner = item['owner']
                        xml += '\t<owner>\n'
                        xml += '\t\t<id>'+owner['id']+'</id>\n'
                        xml += '\t\t<first_name>'+owner['first_name']+'</first_name>\n'
                        xml += '\t\t<last_name>'+owner['last_name']+'</last_name>\n'
                        xml += '\t</owner>\n'

                # az fields
                if endpoint['path'] == 'az':
                    xml += '\t<url>'+item['url']+'</url>\n'
                    xml += '\t<updated>'+item['id']+'</updated>\n'
                    if item['az_vendor_name']:
                        xml += '\t<az_vendor_name>'+item['az_vendor_name']+'</az_vendor_name>\n'
                    else:
                        xml += '\t<az_vendor_name></az_vendor_name>\n'                
                
                xml += '</item>\n'

        xml += '</' + endpoint['path'] + '>\n'

        # Write xml to file...
        filepath = os.path.join(os.path.dirname(__file__), local_directory)
        # config_file_path = os.path.join(os.path.dirname(__file__), 'config.ini')

        with open(filepath + 'lib_guide.xml', 'w') as xml_file:    
            xml_file.write(xml)
            xml_file.close()

        json_results = 'Json iterated into XML.\r\nCount: '+ counter   
    except Exception as e:
        json_results = "Json iteration failed. Exception ", e

# sftp xml file to server01
def sftp_libguide_xml(sftp_host, sftp_port, sftp_user_id, sftp_password, sftp_destination_dir, local_dir):

    sftp_results = '\r\nSFTP\r\n'

    try:
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_client.connect(sftp_host, sftp_port, username=sftp_user_id, password=sftp_password)
        sftp = ssh_client.open_sftp()
        # now = datetime.now() # current date and time
        current_filename = 'lib_guide.xml'
        local_filepath = os.path.join(local_dir, current_filename)
        destination_filepath = os.path.join(sftp_destination_dir, current_filename)
        match = 0

        with os.scandir(local_dir) as entries:
            for entry in entries:       
                if(entry.name == current_filename):
                    match = 1

        if (match == 1):
        
            sftp.put(local_filepath, destination_filepath)
            sftp_results += 'local file: ' + local_filepath + '\r\ndestination file: ' + destination_filepath + '\r\n'  
        
        else: 
        
            sftp_results += 'No file match found\r\n'
        
        # Close
        if sftp: sftp.close()

    except Exception as err:
        print("Error ", err.args)

if __name__ == '__main__':

    try: 
        # Access configuration information
        cfg = configparser.ConfigParser()
        config_file_path = os.path.join(os.path.dirname(__file__), 'config.ini')
        cfg.read(config_file_path)
        sftp_host = cfg.get('DEFAULT', 'sftp_host')
        sftp_port = cfg.get('DEFAULT', 'sftp_port')
        sftp_user_id = cfg.get('DEFAULT', 'sftp_user_id')
        sftp_password = cfg.get('DEFAULT', 'sftp_password')
        sftp_target_directory = cfg.get('DEFAULT', 'sftp_target_directory')
        local_dir = cfg.get('DEFAULT', 'local_directory')
        local_directory = os.path.join(os.path.dirname(__file__), local_dir)
        email_recipient = cfg.get('DEFAULT', 'email_recipient')
        email_sender = cfg.get('DEFAULT', 'email_sender')
        email_title = cfg.get('DEFAULT', 'email_title')

        # Current date
        now = datetime.now()
        today = now.strftime('%Y_%m_%d')
        msg = 'Date: ' + today + '\r\n'

        # Acquire token
        token = acquire_token()

        if token == 'error':
            msg += 'There was an error acquiring the token. \r\n'    
        else:
            # guides, az, subjects
            endpoint = { 'path':'guides', 'expansion': '?expand=owner&status[0,1,2,3]&pages'}
        
            json_data = access_endpoint(token, endpoint)
            if json_data != '':
                json_results = iterate_json(endpoint, json_data, local_directory, today)

        time.sleep(3)
    
        sftp_results = sftp_libguide_xml(sftp_host, sftp_port, sftp_user_id, sftp_password, sftp_target_directory, local_directory)
        msg = msg + "File created: " + sftp_host + ": " + sftp_target_directory

        mail = Mailer(email_sender, email_recipient, email_title, msg)
        mail.email_notification()
    
    except Exception as err1:
            print("Error 1 ", err1) 


