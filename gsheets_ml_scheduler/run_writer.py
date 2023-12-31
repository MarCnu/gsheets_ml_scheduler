try:
  from google.colab import auth as colab_auth
  from google.auth import default as google_auth_default
  is_colab = True
except:
  is_colab = False

import gspread
from gspread.utils import rowcol_to_a1

class GSheetsMLRunWriter():
  def __init__(self, gsheets_file_url, sheet_index=0, service_account_json_path=None):
    """
    gsheets_file_url (str): The URL of the Google Sheets file
    sheet_index (int, optional): In case you don't want to use the default "Sheet1" tab (default is 0)
    service_account_json_path (str, optional): Set to None (default) to get a popup asking to give this Colab instance the right to modify a Google Account (the right is revoked when the broswer tab is closed)
                                                      Set to a path to the file 'service_account.json' to connect to Google's APIs without Colab. Even to read/write a publicly modifiable Google Docs file, bots need a Google Service Account key
    """
    self.gsheets_file_url = gsheets_file_url
    self.service_account_json_path = service_account_json_path

    self.colors = {
      "new_column_name": {'red': 0.9, "green": 0.9, "blue": 0.9}
    }
    
    self.all_sheets = self.login_and_get_sheets()
    self.sheet_index = sheet_index
    self.sheet = self.all_sheets.worksheets()[self.sheet_index]

    print(f'Run Writer connected to GSheet')

  def login_and_get_sheets(self):
    """
    This opens a popup to give your Colab file the reading/writing rights on the GSheets file
    Access rights do not persist after you close the Colab browser tab
    Rights are only given to that specific Colab browser tab

    This uses colab.auth library
    """
    if self.service_account_json_path is None: # Use Google Docs Sheets API through Colab
      if not is_colab:
        print("This isn't running on Colab. Outside of Colab, you must use 'service_account_json_path' to authenticate")
        raise(Exception("NotColabNorServiceAccountError"))
      colab_auth.authenticate_user() # That line is the only part that is Colab specific. Popup that asks for the right to modify a Google Account
      credentials, _ = google_auth_default()
      gclient = gspread.authorize(credentials)
    else: # Use Google Docs Sheets API with a Google Service Account key
      gclient = gspread.service_account(filename=self.service_account_json_path)
    
    all_sheets = gclient.open_by_url(self.gsheets_file_url)
    return all_sheets
  
  def write_runs(self, configs):
    """
    configs (list): A list of config dictionaries (they can contains the "run_name" key/value).
                            It CANNOT contain the keys "status" and "worker_name"
    
    This first downloads the sheet content to find where the config column names are located and how many lines there currenlty are
    """
    # Generic data preprocessing
    data = self.sheet.get_all_values()

    size = (len(data), len(data[0]))
    keys = data[0]

    key_ids = {}
    for i in range(size[1]):
      key_ids[keys[i]] = i
    
    self.size = size
    self.nb_runs = size[0]-2 # Not used in this code, but useful for users to iterate over get_run_config(run_id)
    self.keys = keys # All colmun names
    self.key_ids = key_ids # Key to column number conversion

    def get_update_col_dict(line_start_python, n_lines, col_python, value_list):
        cell_name_start = rowcol_to_a1(1+line_start_python, 1+col_python)
        cell_name_end = rowcol_to_a1(1+line_start_python+n_lines-1, 1+col_python)
        values = []
        for value in value_list:
          values.append([value])
        return {'range': f'{cell_name_start}:{cell_name_end}', 'values': values}

    updated_keys = set()
    for i, config in enumerate(configs):
      # We add a number as default run_name
      if "run_name" not in config:
        first_new_run_id = size[0] - 2
        config["run_name"] = first_new_run_id + i
      
      config["status"] = "ready"

      updated_keys.update(config.keys()) # Reminder: it's a set not a list

      # Create new columns in the sheet if some config keys don't exist
      for key in config.keys():
        if key not in keys:
          cell_name = rowcol_to_a1(1, 1+len(keys))
          self.sheet.format(cell_name, {"backgroundColor": self.colors["new_column_name"]}) # New column gray
          
          self.sheet.update_cell(1, 1+len(keys), key)
          key_ids[key] = len(keys)
          keys.append(key)
          
    # To avoid Sheets API spam limit, we do a batch_update, column by column
    cell_updates = []
    for key in updated_keys:
      values_list = []
      for conf in configs:
        values_list.append(conf[key] if key in conf else "")
      cell_updates.append(get_update_col_dict(size[0], len(configs), key_ids[key], values_list))
    self.sheet.batch_update(cell_updates)
