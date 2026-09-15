## Pieces of the puzzle

Once the server is broken down into its main components, it becomes obvious why a single backup method is not necessarily the best approach. An operating system, a database, a Docker environment and an ordinary collection of files do not have the same recovery requirements. Treating them as though they do can waste storage space, increase recovery time, or leave important parts of the system difficult to reconstruct.

### The operating system

Backing up the operating system is not simply a matter of copying `/etc`, `/usr` and a few other directories.

A working server also depends on its disk layout, RAID configuration, filesystems, bootloader, EFI setup, network configuration, firewall rules, users and groups, installed packages, services, scheduled tasks, permissions and a large number of configuration files. Many of these are individually easy to recreate. The problem is recreating all of them correctly, in the right order, and quickly enough to return the server to service.

A normal file backup can preserve much of this information, but it does not by itself recreate the machine needed to use those files. Before the backup can even be restored, the replacement server must normally be partitioned, filesystems created, RAID arrays assembled, an operating system installed, networking configured and enough of the environment rebuilt to allow the restore to proceed.

This is where bare-metal recovery differs from ordinary file recovery. What we really want is not only a copy of the operating-system files, but enough information to reconstruct the system around them.

That requirement leads naturally to tools such as **ReaR — Relax-and-Recover**, which are designed specifically around recreating a Linux system rather than simply archiving its files. We will look at ReaR in more detail when we get to the recovery strategy.

### Databases

Databases pose a very different problem.

The MariaDB data on this server is measured in hundreds of gigabytes and is continually changing as new information is added. Simply copying the live database directory is therefore not equivalent to backing up an ordinary collection of files. The backup has to represent a consistent database state and, just as importantly, it has to be recoverable within an acceptable amount of time.

There are two main approaches worth considering here.

The first is a **logical backup**, using a tool such as `mariadb-dump`. The result is SQL that can be imported into a newly created database. Logical backups are relatively simple, portable and easy to understand. They also make it possible to separate the schema from the data and to split very large tables into smaller restore units.

The disadvantage becomes apparent when the database is large: restoration can be slow. Hundreds of gigabytes of SQL have to be parsed and executed again, indexes maintained or rebuilt, and every row inserted back into the database engine.

Long restore times introduce another practical problem. If a large monolithic import fails or is interrupted several hours into the process, the destination may be left only partially restored. Depending on how the backup was structured, the safest option may be to clean up the incomplete restore and begin again.

This is one reason the logical backup procedure used for the large `metrics` database does not place everything into one enormous file. The schema, ordinary tables and large tables are separated, while the particularly large `daily_requests` table is divided into individual monthly dumps. That does not make SQL restoration fast, but it makes the process much more manageable and gives us smaller recovery units instead of one all-or-nothing import.

The other approach is a **physical backup**, using `mariadb-backup`. Instead of recreating the database through SQL statements, a physical backup works with the database files themselves.

This is more involved. The backup has to be prepared correctly before restoration, and the process is more closely tied to MariaDB's physical storage and version compatibility. The attraction, however, is recovery speed. Restoring physical database files can be considerably quicker than replaying hundreds of gigabytes of SQL.

The tradeoff is therefore not simply one backup tool against another. Logical backups favour portability and simplicity; physical backups favour faster recovery. With sufficiently large databases, restore time becomes important enough that both approaches deserve consideration.

### Docker

Docker introduces yet another set of decisions.

At first glance, `/var/lib/docker` looks like one large block of data that should simply be backed up. On this server it currently occupies around **436 GB**. Looking more closely, however, shows why that would be a poor assumption.

Docker reports roughly 36 GB of images, 24 GB of local volumes and less than 1 GB of container writable data, but around **362 GB is build cache**. More than 333 GB of that cache is considered reclaimable by Docker itself.

That distinction matters. A build cache may consume disk space, but it does not necessarily represent irreplaceable data.

The same applies to some images and containers. If an image can be rebuilt or downloaded again, keeping every historical copy in the disaster-recovery backup may achieve little except consuming storage.

The situation is not quite as simple as throwing Docker away and rebuilding everything from source either. On this server, containerized applications provide specific working environments, and those environments continue to evolve as the applications are developed. Source code may be available from Git repositories, but rebuilding every container, restoring its configuration and reconnecting it to its data adds extra steps during an outage.

For disaster recovery, the important question is therefore not **"How large is `/var/lib/docker`?"** but rather **"Which parts of it do we actually need in order to return the applications to service quickly?"**

That distinction between *occupied space* and *recoverable state* will become important when we decide exactly what is worth sending to remote storage.

### Ordinary files

Not everything on the server requires a specialised backup method.

Website files, application source, scripts, user data and other ordinary filesystem content can generally be archived and restored in a conventional way. They still need to retain permissions, ownership and other filesystem attributes, but they do not have the transactional consistency requirements of a live database.

These files are therefore good candidates for inclusion with the operating-system recovery set, provided there is enough space and no particular reason to handle them separately.

### Compression

Finally, there is compression.

With remote storage capacity deliberately constrained, compression is not merely a convenience. It is part of the strategy.

Logical SQL dumps compress particularly well because SQL contains large amounts of repetitive text. The current MariaDB backup scripts therefore stream the output of `mariadb-dump` directly through `gzip`, avoiding the need to first write a potentially enormous uncompressed SQL file to disk.

The same principle can be applied to other filesystem data where compression is effective.

There is, of course, a tradeoff. Compression consumes CPU time during backup and decompression adds work during recovery. The question is whether the reduction in storage and transfer requirements outweighs that cost. Under a tight remote-storage limit, the answer is often yes.

What we are left with is not one backup problem but several: reconstructing the server itself, restoring very large databases, preserving the parts of Docker that matter, and archiving ordinary files efficiently. The next step is to match each of those problems to the most appropriate recovery method and combine them into one workable strategy.
