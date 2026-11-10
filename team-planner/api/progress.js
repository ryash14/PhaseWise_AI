// Shared progress for the Team Planner (Vercel serverless function).
// Stores ticks in Upstash Redis (Vercel Marketplace). Without Redis it answers 503
// and the site falls back to saving ticks in each browser.

const TEAM_PASSWORD = "123456";
const KEY = "phasewise:progress";
const OWNERS = {
  "persistence/database.py": "yashwanth",
  "persistence/models.py": "yashwanth",
  "persistence/repository.py": "yashwanth",
  "access/password_security.py": "yashwanth",
  "run_database_setup.py": "yashwanth",
  "agentic/state.py": "yash",
  "tools/decision_tools.py": "yash",
  "knowledge/pdf_extraction.py": "janavi",
  "knowledge/chunk_splitting.py": "janavi",
  "dashboard/api_client.py": "aparna",
  "dashboard/sign_in.py": "aparna",
  "data_pipeline/dataset_loader.py": "karthik",
  "data_pipeline/common_cleaning.py": "karthik",
  "data_pipeline/application_cleaning.py": "karthik",
  "data_pipeline/document_cleaning.py": "karthik",
  "tools/application_data_tools.py": "yashwanth",
  "tools/screening_tools.py": "yash",
  "tools/notice_tools.py": "yash",
  "knowledge/standard_reading.py": "janavi",
  "knowledge/vector_index.py": "janavi",
  "dashboard/application_queue.py": "aparna",
  "dashboard/application_detail.py": "aparna",
  "data_pipeline/history_cleaning.py": "karthik",
  "data_pipeline/connection_log_cleaning.py": "karthik",
  "data_pipeline/sentence_cleaning.py": "karthik",
  "data_pipeline/quality_profiler.py": "karthik",
  "run_data_pipeline.py": "karthik",
  "api/schemas.py": "yashwanth",
  "tools/evidence_tools.py": "yash",
  "tools/retrieval_tools.py": "janavi",
  "run_knowledge_indexing.py": "janavi",
  "dashboard/decision_queue.py": "aparna",
  "dashboard/audit_trail.py": "aparna",
  "data_pipeline/feature_builder.py": "karthik",
  "modeling/model_registry.py": "karthik",
  "modeling/model_evaluation.py": "karthik",
  "modeling/network_work_model.py": "karthik",
  "tools/prediction_tools.py": "karthik",
  "access/permissions.py": "yashwanth",
  "agentic/agents.py": "yash",
  "chat/conversation_memory.py": "janavi",
  "chat/record_answer.py": "janavi",
  "dashboard/connection_chat.py": "aparna",
  "modeling/duration_model.py": "karthik",
  "modeling/sentence_model.py": "karthik",
  "run_model_training.py": "karthik",
  "api/routes.py": "yashwanth",
  "run_api_service.py": "yashwanth",
  "agentic/nodes.py": "yash",
  "agentic/graph.py": "yash",
  "chat/connection_assistant.py": "janavi",
  "run_dashboard.py": "aparna"
};

function redisSettings() {
  const url = process.env.KV_REST_API_URL || process.env.UPSTASH_REDIS_REST_URL;
  const token = process.env.KV_REST_API_TOKEN || process.env.UPSTASH_REDIS_REST_TOKEN;
  return url && token ? { url: url.replace(/\/$/, ""), token } : null;
}

async function redis(settings, command) {
  const reply = await fetch(settings.url, {
    method: "POST",
    headers: { Authorization: `Bearer ${settings.token}`, "Content-Type": "application/json" },
    body: JSON.stringify(command),
  });
  if (!reply.ok) throw new Error(`Redis answered ${reply.status}`);
  const data = await reply.json();
  if (data.error) throw new Error(data.error);
  return data.result;
}

function readBody(req) {
  if (req.body && typeof req.body === "object") return req.body;
  try { return JSON.parse(req.body || "{}"); } catch (error) { return {}; }
}

module.exports = async (req, res) => {
  res.setHeader("Cache-Control", "no-store");
  const settings = redisSettings();
  if (!settings) {
    res.status(503).json({ error: "Shared progress is not configured" });
    return;
  }
  try {
    if (req.method === "GET") {
      const flat = (await redis(settings, ["HGETALL", KEY])) || [];
      const done = {};
      for (let i = 0; i < flat.length; i += 2) {
        if (flat[i + 1] === "1" && OWNERS[flat[i]]) done[flat[i]] = true;
      }
      res.status(200).json({ done });
      return;
    }
    if (req.method === "POST") {
      const { username, password, path, done } = readBody(req);
      if (password !== TEAM_PASSWORD || !Object.values(OWNERS).includes(username)) {
        res.status(401).json({ error: "Sign in first" });
        return;
      }
      if (OWNERS[path] !== username) {
        res.status(403).json({ error: "Only the owner of this file can change its progress" });
        return;
      }
      await redis(settings, ["HSET", KEY, path, done ? "1" : "0"]);
      res.status(200).json({ ok: true });
      return;
    }
    res.setHeader("Allow", "GET, POST");
    res.status(405).json({ error: "Method not allowed" });
  } catch (error) {
    res.status(502).json({ error: String(error.message || error) });
  }
};
