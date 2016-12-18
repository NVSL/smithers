from oauth2client.client import GoogleCredentials

def main():
    try:
        credentials = GoogleCredentials.get_application_default()
    except oauth2client.client.ApplicationDefaultCredentialsError as e:
        print("---------------------------------------------------")
        print("- You need to set up Google API credentials       -")
        print("- Please run the command below:                   -")
        print("-      gcloud beta auth application-default login -")
        print("---------------------------------------------------")
        exit(-1)