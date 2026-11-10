import asyncio
from playwright.async_api import async_playwright

html = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
body { font-family: Arial, sans-serif; margin: 40px; color: #222; }
h1 { color: #1e3a8a; margin-bottom: 5px; }
h2 { color: #1e40af; border-bottom: 1px solid #ddd; padding-bottom: 4px; margin-top: 20px; font-size: 16px; }
.contact { font-size: 13px; color: #555; margin-bottom: 15px; }
p, li { font-size: 13px; line-height: 1.5; }
</style>
</head>
<body>
<h1>Sachin Sharma</h1>
<div class="contact">sachin.dev001@example.com | +1-555-839-2041 | San Francisco, CA | Full Stack & AI Systems Engineer</div>
<h2>Professional Summary</h2>
<p>Results-driven Full Stack & AI Systems Engineer with 3.5 years of experience building resilient cloud applications, autonomous web agents, and high-performance REST APIs using Python, FastAPI, React, Docker, and PostgreSQL.</p>
<h2>Technical Skills</h2>
<p><strong>Languages & Frameworks:</strong> Python, FastAPI, Django, JavaScript, TypeScript, React, Node.js, HTML, CSS, SQL</p>
<p><strong>Cloud & DevOps:</strong> Docker, Kubernetes, AWS, PostgreSQL, MongoDB, Redis, Git, CI/CD, Linux</p>
<p><strong>AI & Automation:</strong> LangChain, Machine Learning, Deep Learning, Playwright, Selenium, REST API</p>
<h2>Work Experience</h2>
<p><strong>Senior Full Stack Engineer &mdash; NexaTech Labs (2022 &ndash; Present | 2.5 years)</strong></p>
<ul>
  <li>Built and scaled high-throughput microservices with FastAPI and PostgreSQL, serving 500k+ monthly requests.</li>
  <li>Developed responsive candidate consoles using React, JavaScript, and Tailwind CSS.</li>
  <li>Integrated autonomous AI job discovery and agentic workflow orchestration pipelines.</li>
</ul>
<p><strong>Software Engineer &mdash; DataSphere Systems (2021 &ndash; 2022 | 1.0 year)</strong></p>
<ul>
  <li>Developed scalable RESTful backend services and relational database schemas.</li>
  <li>Implemented automated integration test suites with 92% code coverage.</li>
</ul>
<h2>Education</h2>
<p><strong>Bachelor of Science in Computer Science (B.S.)</strong> &mdash; University of Technology, 2021</p>
</body>
</html>"""

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(html)
        await page.pdf(path='D:/ai-job-agent/sample_resume.pdf')
        await page.pdf(path='D:/ai-job-agent/backend/data/sample_resume.pdf')
        await browser.close()
    print("PDF generation success!")

if __name__ == "__main__":
    asyncio.run(main())
