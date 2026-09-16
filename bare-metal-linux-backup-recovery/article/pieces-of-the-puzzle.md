## Pieces of the puzzle

A production server is made up of separate components, each with its own failure modes and recovery requirements. A configuration file, a database, a container environment and the operating system itself cannot necessarily be protected—or restored—using the same method. Together, those differences can make recovery a real headache, especially in the rare case of a complete system failure.

In the simplest case, a configuration file may have been overwritten or become corrupted after an update. A backup copy allows it to be restored to a prior working condition. But a corrupted table in a database is not so straightforward. You cannot safely treat a table like an ordinary file and simply drop in an older copy. Depending on the structure of the database, there may be foreign key constraints or IDs that did not exist in the older version but are now referenced by other tables. Restoring one table without understanding those relationships can create inconsistencies elsewhere and leave the database out of sync.

An even worse case is operating system failure. Some errors may still be recoverable, but an unbootable or badly damaged operating system usually means rebuilding the machine from scratch unless a proper recovery procedure has already been put in place. This level of OS collapse could be due to a disk failure, an upgrade that didn't complete properly, or often, human error such as bad settings in vital configuration files, a misbehaving script that wasn't properly tested, or as simple as the deletion of crucial files.

Before choosing the backup strategy and tools, we need to fully examine and understand each piece of the puzzle in order to determine which components can be rebuilt, which must be restored, what consistency requirements they have and how they fit into the overall recovery sequence.

### The operating system

At first glance, the operating system is probably the least unusual part of the server. It is a fairly standard AlmaLinux installation running Apache, MariaDB and PHP for the few conventional websites hosted on the machine. There is no mail service, which removes an entire layer of mailboxes, IMAP/SMTP services, spam filtering and related configuration from the recovery problem.

Webmin and Virtualmin provide the GUI management layer, although many administration tasks are still carried out directly from the command line. Over time, that means the system has accumulated the usual mixture of package installations, service settings, scheduled jobs, permissions, firewall rules, network configuration and application-specific changes that turn a stock operating system into a production server.

That is where recovery becomes more complicated.

Reinstalling AlmaLinux itself would not be difficult. Reproducing the server exactly as it was before a failure is another matter. Apache has to come back with the correct virtual hosts and configuration. PHP has to be available in the versions required by the host-level sites. MariaDB has to be installed and configured correctly before its data can be restored. Users, groups, permissions, cron jobs, firewall rules, network settings, service enablement and the numerous configuration files under /etc all have to return in a consistent state.

The storage layout adds another requirement. /var/lib is intentionally mounted on a separate XFS filesystem backed by its own RAID1 array rather than being part of the root filesystem. This allows the databases, Docker data and local backups stored there to grow independently of the operating system. That separation provides a degree of failure containment. If /var/lib fills because a database or container workload grows unexpectedly, it does not automatically consume the remaining free space on '/' and take the operating system down with it.

From a recovery point of view, however, the same separation means the storage layout has to be recreated correctly before the application state can be put back. The RAID array has to exist, the filesystem has to be created, and /var/lib has to be mounted in the correct place before MariaDB data and the required Docker state can be restored.

So the operating-system problem is not simply a matter of keeping copies of /etc or reinstalling a few packages. A successful recovery has to recreate a bootable system with the correct disk layout, filesystems, mounts, packages, services and configuration so that the application layers can be restored on top of it.

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

MariaDB's native 'mariadb-backup' utility takes a different approach. Instead of recreating the database through SQL, it works with the physical database files.

The main attraction is recovery speed. Restoring prepared database files can be considerably faster than rebuilding hundreds of millions of rows through SQL statements.

That speed comes with different requirements.

A full physical backup can require a large amount of working space if it is first written locally before being moved elsewhere. Compression can reduce the final size, but if the backup is created first and compressed afterwards, the server still needs enough free space to hold the uncompressed backup while that process takes place.

Streaming a physical backup directly to another destination can reduce the local-space requirement, but it also makes the backup and restore procedure more involved. Keeping several historical full physical backups would consume substantial storage, while incremental backups reduce that requirement at the cost of a more complicated backup chain.

`mariadb-backup` therefore favours faster recovery, but introduces additional storage and operational complexity.

For a database of this size, the important question is not simply how easy the backup is to create. The restore path matters just as much. Logical backups favour simplicity and portability; physical backups favour recovery speed.
