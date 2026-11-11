# APS Jobs auto filter

  This script automates the retrieval of new and current job listings from the APS Jobs website.

  The purpose of this script is threefold:
1. avoid visiting the APS jobs site daily to view new jobs
2. keep abreast of jobs which are closing soon
3. view job listings on a single page with expanding menus - to avoid endless navigation, tabs and reloading search results to get back to result #50

# Why
The APS Jobs website is pretty functional but there were a couple of things that always annoyed me.
1. You have to log in to save searches but it never lets you stay logged in.
2. It lazily loads entries in a search (defaults to 15 entries to a veiw). When navigating to a listing and then hitting the back button, you often need to reload all of the listings > 15 to get back to the same place.
3. Job titles are often ambiguous so skimming descriptions quickly on one page is a very useful feature.  
4. There are some types of jobs I'm never interested in seeing (EOIs for temporary transfers etc)  

# How
This script just executes a series of requests against the APS Jobs Salesforce API to execute pre-defined queries. It is just an efficiency enhancement to avoid repeated querying every day and avoid logging in to the website. It also provides a historical record of query results and formats the output in a way that I find more convenient to navigate.
I interrogated the API manually through dev tools in chrome and by sending some pretty shoddily constructed curl requests to work out the salesforce API. It's probably documented somewhere, but it was easy enough to figure out with a bit of assistance from copilot.
Thankfully, API responses naturally reveal a lot of the back end data such as query filters, so building a sensible query was not overly challenging.


# Usage:

This script is executed daily as a cron job and produces a daily job listing in html format, and also overwrites an index.html file which is mounted in a docker hosted simple http server. 
The script runs daily at 4am to capture all new listings.

The script interrogates the Salesforce API that hosts the APS jobs website to run a preformatted query (a couple actually, including one which searches only for jobs closing in the next seven days sorted by closing date).

# FIXME: 
- Include sample output
- Include sample crontab entry and links to working docker image for webserver (although any will do)
- Break down API request format in more detail either here or in the script itself.
  
