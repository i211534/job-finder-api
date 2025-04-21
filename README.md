# job-finder-api
A job search API based on FastAPI that scrapes listings from sites such as LinkedIn and Indeed. It sifts through jobs for users according to their criteria with AI-driven relevance scoring and returns suitable recommendations.

## 📸 API Testing Examples

Example1:

![Part 1](./screenshots/job-api-example1-part1.png)
![Part 2](./screenshots/job-api-example1-part2.png)
![Part 3](./screenshots/job-api-example1-part3.png)
![Part 4](./screenshots/job-api-example1-part4.png)

Example2:

![Part 1](./screenshots/job-api-example2-part1.png)
![Part 2](./screenshots/job-api-example2-part2.png)
![Part 3](./screenshots/job-api-example2-part3.png)
![Part 4](./screenshots/job-api-example2-part4.png)

# Sample request/response

Requests:
{
    "position": "Frontend Developer",
    "experience": "2 years",
    "salary": "50000 - 150000",
    "jobNature": "onsite",
    "location": "pakistan",
    "skills": "React"
}

Response:
{
    "relevant_jobs": [
        {
            "job_title": "Sr. FrontEnd Developer (Angular/Threejs)",
            "company": "Pakistan Recruitment",
            "location": "Lahore, Pakistan",
            "jobNature": "onsite",
            "experience": "",
            "apply_link": "https://www.google.com/search?q=Sr.+FrontEnd+Developer+(Angular/Threejs)+Pakistan+Recruitment+job",
            "salary": ""
        },
        {
            "job_title": "Frontend developer Intern",
            "company": "One Tech and AI",
            "location": "Peshawar",
            "jobNature": "onsite",
            "experience": "1-3 years",
            "apply_link": "https://pk.linkedin.com/jobs/view/frontend-developer-intern-at-one-tech-and-ai-4213853359?utm_campaign=google_jobs_apply&utm_source=google_jobs_apply&utm_medium=organic",
            "salary": "79,125.00 PKR"
        },
        {
            "job_title": "Junior Front End Developer",
            "company": "Translation Empire PK",
            "location": "Rawalpindi, Pakistan",
            "jobNature": "onsite",
            "experience": "",
            "apply_link": "https://www.google.com/search?q=Junior+Front+End+Developer+Translation+Empire+PK+job",
            "salary": ""
        },
        {
            "job_title": "Front-End / Full-Stack Developer",
            "company": "Securiti.ai",
            "location": "Karachi, Pakistan",
            "jobNature": "onsite",
            "experience": "",
            "apply_link": "https://www.google.com/search?q=Front-End+/+Full-Stack+Developer+Securiti.ai+job",
            "salary": ""
        },
        {
            "job_title": "MERN Stack Developer Frontend Engineer",
            "company": "BJS Soft Solutions",
            "location": "Pakistan",
            "jobNature": "onsite",
            "experience": "",
            "apply_link": "https://www.google.com/search?q=MERN+Stack+Developer+Frontend+Engineer+BJS+Soft+Solutions+job",
            "salary": ""
        },
        {
            "job_title": "Front-end Developer in Karachi |  Webnet Pakistan",
            "company": "Webnet Pakistan Pvt Ltd",
            "location": "Karachi, Pakistan",
            "jobNature": "onsite",
            "experience": "",
            "apply_link": "https://www.google.com/search?q=Front-end+Developer+in+Karachi+|++Webnet+Pakistan+Webnet+Pakistan+Pvt+Ltd+job",
            "salary": ""
        },
        {
            "job_title": "Front-end UI Developer",
            "company": "Life @ Get Licensed",
            "location": "PK",
            "jobNature": "onsite",
            "experience": "1-3 years",
            "apply_link": "https://pk.linkedin.com/jobs/view/front-end-ui-developer-at-life-%40-get-licensed-4190594057?utm_campaign=google_jobs_apply&utm_source=google_jobs_apply&utm_medium=organic",
            "salary": "79,125.00 PKR"
        },
        {
            "job_title": "Junior Front End Developer",
            "company": "Translation Empire PK",
            "location": "Rawalpindi",
            "jobNature": "onsite",
            "experience": "1-3 years",
            "apply_link": "https://pk.linkedin.com/jobs/view/junior-front-end-developer-at-translation-empire-pk-4166896822?utm_campaign=google_jobs_apply&utm_source=google_jobs_apply&utm_medium=organic",
            "salary": "79,125.00 PKR"
        }
    ]
}

Request:
{
    "position": "Backend Developer",
    "experience": "2 years",
    "salary": "50000 - 150000",
    "jobNature": "remote",
    "location": "usa",
    "skills": "Python, Django, REST APIs"
}

Response:
{
    "relevant_jobs": [
        {
            "job_title": "Backend Developer, Remote",
            "company": "Active Theory",
            "location": "Los Angeles, California",
            "jobNature": "remote",
            "experience": "1-3 years",
            "apply_link": "https://www.indeed.com/viewjob?jk=c826c4f3d621683b&utm_campaign=google_jobs_apply&utm_source=google_jobs_apply&utm_medium=organic",
            "salary": "$101,289.11"
        },
        {
            "job_title": "Contract AWS Backend Developer",
            "company": "The Motley Fool",
            "location": "Remote, Oregon",
            "jobNature": "remote",
            "experience": "1-3 years",
            "apply_link": "https://www.indeed.com/viewjob?jk=48e7823c51afd3dc&utm_campaign=google_jobs_apply&utm_source=google_jobs_apply&utm_medium=organic",
            "salary": "$101,289.11"
        },
        {
            "job_title": "Backend Developer, Remote",
            "company": "Active Theory",
            "location": "Los Angeles, CA",
            "jobNature": "remote",
            "experience": "",
            "apply_link": "https://www.google.com/search?q=Backend+Developer,+Remote+Active+Theory+job",
            "salary": ""
        },
        {
            "job_title": "Backend Developer, Remote",
            "company": "Active Theory",
            "location": "Not specified",
            "jobNature": "remote",
            "experience": "",
            "apply_link": "https://www.google.com/search?q=Backend+Developer,+Remote+Active+Theory+job",
            "salary": "80,811–121,217 a year"
        },
        {
            "job_title": "Senior .NET Backend Developer – iGaming / Sportsbook (Fully Remote)",
            "company": "Playnetic",
            "location": "Malta, OH",
            "jobNature": "remote",
            "experience": "",
            "apply_link": "https://www.google.com/search?q=Senior+.NET+Backend+Developer+–+iGaming+/+Sportsbook+(Fully+Remote)+Playnetic+job",
            "salary": ""
        },
        {
            "job_title": "Backend Developer (Remote Option)",
            "company": "Trinnex",
            "location": "Not specified",
            "jobNature": "remote",
            "experience": "",
            "apply_link": "https://www.google.com/search?q=Backend+Developer+(Remote+Option)+Trinnex+job",
            "salary": "80,811–121,217 a year"
        },
        {
            "job_title": "Remote Back-End Developer Intern (Node.js)",
            "company": "BottleUp",
            "location": "Washington, DC",
            "jobNature": "remote",
            "experience": "",
            "apply_link": "https://www.google.com/search?q=Remote+Back-End+Developer+Intern+(Node.js)+BottleUp+job",
            "salary": ""
        },
        {
            "job_title": "Senior Backend Engineer, Connectivity (Remote Work Available)",
            "company": "Lensa",
            "location": "Orlando, Florida",
            "jobNature": "remote",
            "experience": "1-3 years",
            "apply_link": "https://www.linkedin.com/jobs/view/senior-backend-engineer-connectivity-remote-work-available-at-lensa-4212602190?utm_campaign=google_jobs_apply&utm_source=google_jobs_apply&utm_medium=organic",
            "salary": "$101,289.11"
        }
    ]
}



