## Lay of the land

The server used for this case study is not a typical website-hosting server. It does host a couple of websites, but its main role is to run a number of web applications that are continually being developed and updated.

Many of those applications depend on large databases that continue to grow as new data is collected daily. Because each application has its own runtime requirements and version dependencies, it is easier to deploy them inside Docker containers where each environment can be specifically tuned. This also relieves the burden of trying to concurrently maintain several versions of Python or PHP, and their associated libraries and package managers on the host operating system. The result is a production system whose state is spread across the operating system, application files, database data, container environments, and a large amount of supporting configuration.

