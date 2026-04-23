export interface AdministratorProperties {
  status_code: number;
  message:     string;
  data:        Data;
}

export interface Data {
  content: Content[];
  count:   number;
}

export interface Content {
  username:   string;
  status:     string;
  updated_at: string | null;
  password:   string;
  uuid:       string;
  id:         number;
  role:       string;
  created_at: string | null;
  deleted_at: string | null;
}
