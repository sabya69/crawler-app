async function startCrawl() {
  const url = document.getElementById("url").value;
  const depth = document.getElementById("depth").value;
  document.getElementById("crawledLinks").innerHTML = "";
  document.getElementById("markupIssues").innerHTML = "";
  document.getElementById("progressFill").style.width = "0%";
  document.getElementById("progressFill").textContent = "0%";

  try {
    const response = await fetch("/crawl", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ url, depth }),
    });

    const data = await response.json();

    // Display markup issues
    data.issues.forEach((issue) => {
      document.getElementById("markupIssues").innerHTML += `<div>${issue}</div>`;
    });

    // Display broken links
    data.broken.forEach((link) => {
      document.getElementById("crawledLinks").innerHTML += `<div style="color: red;">[Broken] ${link}</div>`;
    });

    // Fill progress bar
    const percent = Math.floor((data.progress.done / data.progress.total) * 100);
    document.getElementById("progressFill").style.width = percent + "%";
    document.getElementById("progressFill").textContent = percent + "%";
  } catch (err) {
    alert("❌ Failed to crawl.");
    console.error(err);
  }
}
