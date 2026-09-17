## Pieces of the puzzle

A production server is made up of separate components, each with its own failure modes and recovery requirements. A configuration file, a database, a container environment and the operating system itself cannot necessarily be protected—or restored—using the same method. Together, those differences can make recovery a real headache, especially in the rare case of a complete system failure.

In the simplest case, a configuration file may have been overwritten or become corrupted after an update. A backup copy allows it to be restored to a prior working condition, but a corrupted table in a database is not so straightforward: you cannot just treat a table like an ordinary file and simply drop in an older copy. Depending on the structure of the database, there may be foreign key constraints or IDs that did not exist in the older version but are now referenced by other tables, and restoring one table without understanding those relationships can create inconsistencies elsewhere and leave the database out of sync.

An even worse case is operating system failure. Some errors may still be recoverable, but an unbootable or badly damaged operating system usually means rebuilding the machine from scratch unless a proper recovery procedure has already been put in place. This level of OS collapse could be due to a disk failure, an upgrade that didn't complete properly, or often, human error such as bad settings in vital configuration files, a misbehaving script that wasn't properly tested, or as simple as the deletion of crucial files.

Before choosing the backup strategy and tools, we need to fully examine and understand each piece of the puzzle in order to determine which components can be rebuilt, which must be restored, what consistency requirements they have and how they fit into the overall recovery sequence.

### The operating system

At first glance, the operating system is probably the least unusual part of the server. It is a fairly standard AlmaLinux installation running Apache, MariaDB and PHP for the few conventional websites hosted on the machine. There is no mail service, which removes an entire layer of mailboxes, IMAP/SMTP services, spam filtering and related configuration from the recovery problem.

Webmin and Virtualmin provide the GUI management layer, although many administration tasks are still carried out directly from the command line. Over time, that means the system has accumulated the usual mixture of package installations, service settings, scheduled jobs, permissions, firewall rules, network configuration and application-specific changes that turn a stock operating system into a production server.

That is where recovery becomes more complicated.

Reinstalling AlmaLinux itself would not be difficult. Reproducing the server exactly as it was before a failure is another matter. Apache has to come back with the correct virtual hosts and configuration. PHP has to be available in the versions required by the host-level sites. MariaDB has to be installed and configured correctly before its data can be restored. Users, groups, permissions, cron jobs, firewall rules, network settings, service enablement and the numerous configuration files under /etc all have to return in a consistent state.

The storage layout adds another requirement. `/var/lib` is intentionally mounted on a separate XFS filesystem backed by its own RAID1 array rather than being part of the root filesystem. This allows the databases, Docker data and local backups stored there to grow independently of the operating system. That separation provides a degree of failure containment. If /var/lib fills because a database or container workload grows unexpectedly, it does not automatically consume the remaining free space on `/` and take the operating system down with it.

From a recovery point of view, however, the same separation means the storage layout has to be recreated correctly before the application state can be put back. The RAID array has to exist, the filesystem has to be created, and `/var/lib` has to be mounted in the correct place before MariaDB data and the required Docker state can be restored.

So the operating-system problem is not simply a matter of keeping copies of `/etc` or reinstalling a few packages. A successful recovery has to recreate a bootable system with the correct disk layout, filesystems, mounts, packages, services and configuration so that the application layers can be restored on top of it.

That is the kind of problem a bare-metal recovery tool is designed to solve.

### Databases

The databases are a very different recovery problem from the operating system.

MariaDB currently occupies roughly **732 GB**, and much of that space is concentrated in a small number of very large tables. The largest contains more than **660 million rows**, while the next largest contains around **28 million**. The databases are also active and continue to grow as new data is collected nightly.

That scale changes the way backups have to be considered.

A database is not just a collection of ordinary files that can be copied and dropped back into place later. The data has to be captured in a consistent state, and the relationships between tables matter. Foreign key constraints, referenced IDs and other dependencies mean that restoring one table in isolation can create inconsistencies elsewhere if the replacement does not match the rest of the database.

For a database of this size, there are two realistic approaches worth considering.

#### Logical backups with 'mariadb-dump'

A logical backup writes SQL that can recreate the database schema and data later.

The main advantages are simplicity and portability. Logical dumps are straightforward to create, easy to inspect, and can be compressed efficiently as they are generated. They can also be split into smaller logical units instead of forcing the entire database into one enormous backup file.

The disadvantage appears during recovery.

Restoring a logical dump means feeding the SQL back through MariaDB and rebuilding the database. Whether the dump uses single-row or extended INSERT statements, the individual rows still have to be processed through the storage engine, written into the tables, and incorporated into the indexes. With hundreds of millions of rows, this can take several hours.

Long imports also increase the cost of an unforeseen interruption. If a very large restore that has been running for hours, fails late in the process, the destination may be left only partially rebuilt. Depending on how the dump was structured, cleanup may be required before another attempt can begin.

Logical backups therefore favour simplicity and flexibility, but the price is paid in restore time.

#### Physical backups with 'mariadb-backup'

MariaDB's native `mariadb-backup` utility takes a different approach. Instead of recreating the database through SQL, it works with the physical database files.

The main attraction is recovery speed. Restoring prepared database files can be considerably faster than rebuilding hundreds of millions of rows through SQL statements, although a `mariadb-backup` copy is not immediately ready to restore. It must be prepared so that the redo information is applied and the files become consistent. If there are any incremental backups, they must also be applied to the base backup in sequence. This adds another layer of operational complexity although recovery is still relatively fast compared to logical backups, especially with very large databases.

That speed comes with different requirements.

A full physical backup can require a large amount of working space if it is first written locally before being moved elsewhere. Compression can reduce the final size, but if the backup is created first and compressed afterwards, the server still needs enough free space to hold the uncompressed backup while that process takes place.

Streaming a physical backup directly to another destination can reduce the local-space requirement, but it also makes the backup and restore procedure more involved. Keeping several historical full physical backups would consume substantial storage, while incremental backups reduce that requirement at the cost of a more complicated backup chain.

`mariadb-backup` therefore favours faster recovery, but introduces additional storage and operational complexity.

For a database of this size, the important question is not simply how easy the backup is to create. The restore path matters just as much. Logical backups favour simplicity and portability; physical backups favour recovery speed.

### Raw source data

Not all of the application data on the server originates in the same way.

Some data is collected from external services and written directly into a database. One example is data retrieved through the Google Ads API, which is processed as it is collected rather than being retained separately in its original form.

The accommodation-booking data is handled differently. Each nightly API collection is first saved as JSON before being processed and imported into MariaDB. Those files are therefore more than temporary working data: they are the raw source from which the corresponding database records can be recreated if necessary.

That is particularly useful because the booking-engine data represents a point-in-time snapshot. Daily request and demand figures are derived by comparing one snapshot with the previous day's, so successfully capturing each snapshot matters. Once it has been saved, however, the JSON can be processed later because the relevant dates and times are already contained in the data.

The raw JSON therefore needs to be protected alongside the database backups. It provides an additional recovery path if database data has to be reconstructed, while other application data that is written directly into a database depends more heavily on the database backup itself.

Other services on the server, including n8n and Weaviate, also interact with application data, but their internal mechanics are not important to the recovery strategy. The objective is simply to make sure that the applications, their configuration and the data they depend on can be restored to a working state.

### Docker containers

Docker is used on this server because the applications it runs have a particularly diverse set of runtime requirements and dependencies.

Different applications may require different versions of PHP, Python, libraries, package managers and supporting components. Trying to satisfy all of those dependencies directly through the host operating system would make the server harder to maintain and increase the risk of one application's requirements conflicting with another's.

Running the applications in separate Docker containers avoids much of that problem. Each application can have its own controlled environment with the versions and dependencies it requires, while the AlmaLinux host remains comparatively simple.

From a recovery point of view, however, Docker introduces another layer that has to be considered.

Reinstalling Docker itself is straightforward. Recreating the exact working application environments is not necessarily so. A usable recovery may need the application code, container or build definitions, configuration, environment settings, persistent volumes or bind-mounted data, and any locally maintained state that is not reproduced simply by pulling an original image again.

At first glance, the obvious solution might be to back up the entire `/var/lib/docker` directory. On this server, that directory currently occupies around **436 GB**, but that figure is misleading if it is treated as the amount of irreplaceable Docker data.

Docker reports roughly:

| Docker data | Approximate size |
| --- | ---: |
| Images | 35.9 GB |
| Containers | 0.6 GB |
| Local volumes | 24.0 GB |
| Build cache | 361.8 GB |

More than **333 GB** of the build cache is considered reclaimable by Docker itself.

That makes an important distinction. A large amount of occupied Docker storage consists of cached build data and older image layers that can be recreated. Backing up every byte under `/var/lib/docker` would therefore consume a large amount of remote storage without necessarily improving recovery.

The more important question is which parts are needed to return the applications to service quickly.

Some of the Docker applications also depend on MariaDB databases running directly on the host rather than maintaining their own database daemon inside the container. That means the application environment and its database are separate recovery components, but they still depend on one another. Restoring the container alone is not enough if the host-level database, credentials, configuration and network access have not also been restored correctly.

Docker therefore simplifies dependency management during normal operation, but it adds another recovery layer. The objective is to preserve enough application state and configuration to recreate each working environment quickly and reconnect it to the services and data it depends on, while keeping the backup footprint as small as possible. That said, it is not necessary to preserve every image, cache and temporary layer that Docker has accumulated.

### Ordinary files

Compared with the operating system, databases and Docker, ordinary files are the easy part of a backup. Source code, scripts and configuration files are usually just text, which makes them easy to inspect, edit, verify and compress.

That does not make them unimportant.

Some of the applications on this server do not need Docker because they are conventional LAMP applications that can use the PHP and supporting software already installed on the host. Their files live under the normal Apache web tree and can therefore be protected with a conventional filesystem backup.

The developers also maintain their source code in GitHub, but that serves a different purpose. A repository protects the development history; a server backup protects the deployed state.

In a perfect world, the two should match exactly. In practice, the production server may contain configuration changes, generated files, uploaded assets or code that has not yet been pushed back to the repository. Even where the repository is completely up to date, rebuilding a failed server by locating and cloning every individual application repository adds unnecessary work to an already time-sensitive recovery.

For that reason, preserving the live application tree is still useful even when the source is safely stored elsewhere.

Administrative and recovery scripts are even more important.

The server uses scripts to automate backups, restore data and process some of the raw information collected by the applications. These files are small and easy to back up, but they may be required before other parts of the system can be restored.

This creates something of a **chicken-and-egg problem**.

For example, if a database table has to be rebuilt from the retained booking-engine JSON, preserving the raw data alone is not enough. The PHP script that parses the JSON, performs the required calculations and writes the results back into MariaDB must also be available. Without that script, the source data may be intact but the recovery process cannot proceed.

The same applies to backup and restore scripts themselves. If they are part of the recovery procedure, they need to be accessible early enough in the process to do their job rather than being buried inside a component that has not yet been restored.

This is why the simplest files to back up are not necessarily the least important. Many are plain-text source code, scripts and configuration files, so they are easy to copy, inspect and compress. But some of them provide the instructions and tools needed to restore everything else.

### The big squeeze

With remote backup space at a premium, compression becomes an important part of the overall strategy. But it is not simply a matter of taking a large file, running it through a compressor and assuming the result will be dramatically smaller. Compression depends heavily on the contents of the file and type of data involved.

Text-based data such as SQL dumps, JSON, logs, source code, and configuration files often compresses extremely well because it contains large amounts of repeated structure and text. Other file types may already be compressed or may contain data that does not compress efficiently, so the reduction can be much smaller, almost negligible. The size of the original data therefore does not necessarily tell us how much backup space it will ultimately consume.

There is also another consideration: **compression itself can require working space**.

A logical MariaDB dump is a good example of how that requirement can be kept small. The output from `mariadb-dump` can be piped directly to a compressor like `gzip`. The full uncompressed SQL dump never has to exist as a separate file on disk. Data is produced by `mariadb-dump`, passed directly to the compressor and written out in compressed form.

A physical backup created with `mariadb-backup` can be handled in several ways. If the full backup is first written locally and then compressed afterwards, the server may temporarily need enough free space for both the physical backup and the compressed archive. On a database already occupying hundreds of gigabytes, that additional headroom can be significant.

That is a consequence of the compression path chosen rather than an inherent requirement of `mariadb-backup`, whose output can indeed be streamed and piped through a compressor so that a complete uncompressed copy does not have to be retained locally. This reduces the temporary storage requirement substantially, although it also makes the backup procedure a little more involved.

The same issue can reappear during recovery. A compressed physical backup may need to be extracted and prepared before MariaDB can use it, and the backup archive, extracted data and final database can potentially compete for space if they all reside on the same storage.

If the backup lives on remote storage and is streamed or extracted directly onto a sufficiently large recovery volume, much of that temporary duplication can be avoided. Where the intermediate files are stored can therefore be just as important as the final compressed size.

Directory trees introduce another practical issue. Compressing thousands of files individually would produce an awkward collection of separate compressed objects and would make transport and recovery unnecessarily cumbersome. A more practical approach is to archive the directory tree using `tar` and compress the resulting stream as part of the same operation.


`tar` preserves the directory structure and file metadata while presenting the backup as a single archive. It can also compress the archive as it is created, so there is no requirement to first create a large uncompressed `.tar` file and then compress it as a separate operation. The result is easier to store, verify, transfer and restore than a directory containing thousands of individual backup files.

Compression therefore does more than reduce the amount of remote storage required; it makes backups easier to handle and transport. It's also not simply about compression ratio, but about the complete path that must be considered as part of the design — how the backup is produced, where temporary data is written, how it is transferred, and how much working space will be required again during recovery.
