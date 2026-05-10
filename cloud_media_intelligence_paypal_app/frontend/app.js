const PLANS = [
  { id: "starter", name: "Starter", price: "9.99", images: 500, videoMinutes: 10, storageGb: 5, featured: false,
    features: ["Basic image labels", "Basic video labels", "Small creator batch", "S3 JSON results", "Email support"] },
  { id: "basic", name: "Basic", price: "24.99", images: 2000, videoMinutes: 30, storageGb: 20, featured: true,
    features: ["Image + video labels", "Transcription", "Basic sentiment", "Captions/subtitles", "Priority queue"] },
  { id: "pro", name: "Pro", price: "49.99", images: 5000, videoMinutes: 100, storageGb: 50, featured: false,
    features: ["Advanced image labels", "Video + speech analysis", "Comprehend NLP", "Repeated phrases", "Searchable metadata"] },
  { id: "business", name: "Business", price: "99.99", images: 15000, videoMinutes: 300, storageGb: 150, featured: false,
    features: ["Bulk upload", "Priority processing", "Larger storage", "Human-review flags", "Business metadata exports"] }
];

const api = (path) => `${window.APP_CONFIG.API_BASE_URL}${path}`;

function renderPlans() {
  const el = document.getElementById("plans");
  el.innerHTML = PLANS.map(plan => `
    <article class="plan-card ${plan.featured ? "featured" : ""}">
      <h3>${plan.name}</h3>
      <div class="price">$${plan.price}</div>
      <p>${plan.images.toLocaleString()} images · ${plan.videoMinutes} video min · ${plan.storageGb}GB storage</p>
      <ul>${plan.features.map(f => `<li>${f}</li>`).join("")}</ul>
      <div id="paypal-${plan.id}" class="paypal-slot"></div>
    </article>
  `).join("");
}

async function createOrder(planId) {
  const response = await fetch(api("/orders"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ planId })
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

async function captureOrder(orderId, jobId) {
  const response = await fetch(api("/orders/capture"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ orderId, jobId })
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

window.initPayPalButtons = function initPayPalButtons() {
  renderPlans();
  PLANS.forEach(plan => {
    paypal.Buttons({
      style: { layout: "horizontal", color: "blue", shape: "pill", label: "pay" },
      createOrder: async () => {
        const data = await createOrder(plan.id);
        window.__lastJobId = data.jobId;
        return data.orderId;
      },
      onApprove: async (data) => {
        const result = await captureOrder(data.orderID, window.__lastJobId);
        document.getElementById("jobId").value = result.jobId;
        document.getElementById("lookupJobId").value = result.jobId;
        alert("Payment captured. Job ID: " + result.jobId + ". Now upload files.");
      },
      onError: (err) => alert("PayPal error: " + err.message)
    }).render(`#paypal-${plan.id}`);
  });
};

document.addEventListener("DOMContentLoaded", () => {
  renderPlans();

  document.getElementById("uploadForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const status = document.getElementById("uploadStatus");
    status.textContent = "Creating upload URLs...\n";
    const jobId = document.getElementById("jobId").value.trim();
    const files = Array.from(document.getElementById("files").files);
    const uploaded = [];

    for (const file of files) {
      const urlRes = await fetch(api("/upload-url"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ jobId, filename: file.name, contentType: file.type || "application/octet-stream", size: file.size })
      });
      if (!urlRes.ok) throw new Error(await urlRes.text());
      const { uploadUrl, s3Key } = await urlRes.json();
      status.textContent += `Uploading ${file.name}...\n`;
      const put = await fetch(uploadUrl, { method: "PUT", headers: { "Content-Type": file.type || "application/octet-stream" }, body: file });
      if (!put.ok) throw new Error("Upload failed for " + file.name);
      uploaded.push({ s3Key, filename: file.name, contentType: file.type, size: file.size });
    }

    status.textContent += "Starting processing workflow...\n";
    const startRes = await fetch(api("/jobs/start"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ jobId, files: uploaded })
    });
    if (!startRes.ok) throw new Error(await startRes.text());
    status.textContent += JSON.stringify(await startRes.json(), null, 2);
  });

  document.getElementById("lookupBtn").addEventListener("click", async () => {
    const jobId = document.getElementById("lookupJobId").value.trim();
    const res = await fetch(api(`/jobs/${encodeURIComponent(jobId)}`));
    document.getElementById("jobStatus").textContent = await res.text();
  });
});
