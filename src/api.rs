use crate::types::{ApiProject, ApiSection, ApiTask, ApiTaskDetail};
use reqwest::Client;
use serde_json::Value;

const BASE_URL: &str = "https://api.todoist.com/api/v1";

#[derive(Clone)]
pub struct ApiClient {
    client: Client,
    token: String,
}

impl ApiClient {
    pub fn new(token: String) -> Self {
        Self { client: Client::new(), token }
    }

    fn auth(&self) -> String {
        format!("Bearer {}", self.token)
    }

    async fn get_paginated<T>(&self, path: &str, params: &[(&str, &str)]) -> Result<Vec<T>, String>
    where
        T: serde::de::DeserializeOwned,
    {
        let mut results: Vec<T> = Vec::new();
        let mut cursor: Option<String> = None;

        loop {
            let mut req = self.client
                .get(format!("{}/{}", BASE_URL, path))
                .header("Authorization", self.auth())
                .query(params);
            if let Some(ref c) = cursor {
                req = req.query(&[("cursor", c.as_str())]);
            }

            let resp = req.send().await.map_err(|e| e.to_string())?;
            resp.error_for_status_ref().map_err(|e| e.to_string())?;
            let data: Value = resp.json().await.map_err(|e| e.to_string())?;

            if let Some(arr) = data.get("results").and_then(|v| v.as_array()) {
                results.extend(arr.iter().filter_map(|v| serde_json::from_value(v.clone()).ok()));
                cursor = data.get("next_cursor").and_then(|v| v.as_str()).map(str::to_owned);
                if cursor.is_none() { break; }
            } else if let Some(arr) = data.as_array() {
                results.extend(arr.iter().filter_map(|v| serde_json::from_value(v.clone()).ok()));
                break;
            } else {
                break;
            }
        }
        Ok(results)
    }

    pub async fn get_projects(&self) -> Result<Vec<ApiProject>, String> {
        self.get_paginated("projects", &[]).await
    }

    pub async fn get_sections(&self, project_id: &str) -> Result<Vec<ApiSection>, String> {
        self.get_paginated("sections", &[("project_id", project_id)]).await
    }

    pub async fn get_tasks(&self, project_id: &str) -> Result<Vec<ApiTask>, String> {
        self.get_paginated("tasks", &[("project_id", project_id)]).await
    }

    pub async fn get_task(&self, task_id: &str) -> Result<ApiTaskDetail, String> {
        let resp = self.client
            .get(format!("{}/tasks/{}", BASE_URL, task_id))
            .header("Authorization", self.auth())
            .send().await.map_err(|e| e.to_string())?;
        resp.error_for_status_ref().map_err(|e| e.to_string())?;
        resp.json::<ApiTaskDetail>().await.map_err(|e| e.to_string())
    }

    pub async fn add_task(
        &self, content: &str, project_id: &str,
        section_id: Option<&str>, description: Option<&str>,
    ) -> Result<ApiTask, String> {
        let mut body = serde_json::json!({ "content": content, "project_id": project_id });
        if let Some(s) = section_id { body["section_id"] = serde_json::json!(s); }
        if let Some(d) = description { body["description"] = serde_json::json!(d); }
        let resp = self.client
            .post(format!("{}/tasks", BASE_URL))
            .header("Authorization", self.auth())
            .json(&body).send().await.map_err(|e| e.to_string())?;
        resp.error_for_status_ref().map_err(|e| e.to_string())?;
        resp.json::<ApiTask>().await.map_err(|e| e.to_string())
    }

    pub async fn close_task(&self, task_id: &str) -> Result<(), String> {
        let resp = self.client
            .post(format!("{}/tasks/{}/close", BASE_URL, task_id))
            .header("Authorization", self.auth())
            .send().await.map_err(|e| e.to_string())?;
        resp.error_for_status_ref().map_err(|e| e.to_string())?;
        Ok(())
    }

    pub async fn reopen_task(&self, task_id: &str) -> Result<(), String> {
        let resp = self.client
            .post(format!("{}/tasks/{}/reopen", BASE_URL, task_id))
            .header("Authorization", self.auth())
            .send().await.map_err(|e| e.to_string())?;
        resp.error_for_status_ref().map_err(|e| e.to_string())?;
        Ok(())
    }

    pub async fn update_task(
        &self, task_id: &str, content: &str, description: Option<&str>,
    ) -> Result<ApiTask, String> {
        let body = serde_json::json!({
            "content": content,
            "description": description.unwrap_or(""),
        });
        let resp = self.client
            .post(format!("{}/tasks/{}", BASE_URL, task_id))
            .header("Authorization", self.auth())
            .json(&body).send().await.map_err(|e| e.to_string())?;
        resp.error_for_status_ref().map_err(|e| e.to_string())?;
        resp.json::<ApiTask>().await.map_err(|e| e.to_string())
    }

    pub async fn delete_task(&self, task_id: &str) -> Result<(), String> {
        let resp = self.client
            .delete(format!("{}/tasks/{}", BASE_URL, task_id))
            .header("Authorization", self.auth())
            .send().await.map_err(|e| e.to_string())?;
        resp.error_for_status_ref().map_err(|e| e.to_string())?;
        Ok(())
    }

    pub async fn move_task(
        &self, task_id: &str,
        section_id: Option<&str>, project_id: Option<&str>,
    ) -> Result<(), String> {
        let mut body = serde_json::json!({});
        if let Some(s) = section_id { body["section_id"] = serde_json::json!(s); }
        else if let Some(p) = project_id { body["project_id"] = serde_json::json!(p); }
        let resp = self.client
            .post(format!("{}/tasks/{}/move", BASE_URL, task_id))
            .header("Authorization", self.auth())
            .json(&body).send().await.map_err(|e| e.to_string())?;
        resp.error_for_status_ref().map_err(|e| e.to_string())?;
        Ok(())
    }
}
