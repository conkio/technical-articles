## Putting the pieces together

We have already seen that this server is a hybrid system in more ways than one, combining a conventional Linux host with Docker-based applications, ordinary LAMP applications, very large databases, raw source data and a separate high-growth filesystem. It follows that the backup strategy also has to be hybrid, with no single backup method that can handle all of those components equally well, especially when the available remote storage is considerably smaller than the server’s usable local storage capacity.

The solution is therefore not to look for one perfect backup tool, but to combine several approaches and use each where it makes the most sense. Some parts of the server need to be captured almost exactly, others can be rebuilt from logical backups, some can even be regenerated from raw data, and some only need their configuration and essential state preserved. The complication is that all of those methods eventually have to come back together in the correct order to recreate a working system.

There is another advantage to breaking the recovery strategy into smaller pieces: maintainability. A programmer would rarely put an entire application into one enormous function, and the same principle applies here. Keeping the backup and restore procedures compartmentalised makes each one easier to understand, test and modify. If the database backup method changes, for example, there should be no need to redesign the operating-system recovery process at the same time. The same applies if more storage is added, a new application is introduced, or one backup tool is eventually replaced by another. A modular recovery plan is easier to maintain today and much easier to adapt tomorrow.

One final item that would be easy to overlook: the recovery plan cannot exist only in the head of the person who designed it. If someone unfamiliar with the server had to take over after a serious failure, they would need enough documentation to understand what has been backed up, where it is stored, which components depend on others, and in what order they must be restored, and the documentation therefore becomes part of the recovery system itself.

### ReaR 2.9

[Relax-and-Recover (ReaR)](https://relax-and-recover.org/rear-user-guide/) is a Linux disaster-recovery framework designed primarily for bare-metal recovery. The version used here is **ReaR 2.9**, which the project lists as supporting RHEL 9 and compatible distributions including AlmaLinux 9.

> “ReaR complements backup and restore of data with bare metal disaster recovery.”
>
> — [ReaR 2.9 release notes](https://relax-and-recover.org/rear-user-guide/releasenotes/rear29.html)

That distinction is important. ReaR is not simply another utility for copying files from one place to another. Its job is to preserve enough information about a working Linux system to recreate the environment those files belonged to if the original machine has to be rebuilt.

#### What ReaR does

During backup preparation, ReaR examines the running system and records its storage layout. That can include disks, partitions, software RAID, filesystems and mount points. It then builds a small bootable Linux recovery environment containing the programs, libraries, kernel modules and configuration required to perform the recovery. The result is a rescue image that can be booted independently of the failed operating system. It is not an image of every byte on the server, but instead provides the environment and recovery information needed to rebuild the machine and restore its protected files.

ReaR separates the **recovery system** from the **data backup** and can integrate with external backup software, leaving that software responsible for restoring the files, or it can use one of its own built-in backup methods. In this case it uses the internal `NETFS` method with `tar`, allowing the selected filesystem content to be stored separately from the bootable ISO.

The [online `rear` man page](https://github.com/rear/rear/blob/master/doc/rear.8.md) describes `mkbackup` as the workflow that creates both the rescue media and the system backup when an internal backup method is being used. The ReaR documentation also distinguishes this from `mkrescue`, which creates the recovery environment without creating the associated data backup.

During a full recovery, the replacement or repaired server is booted from the ReaR rescue image. According to the project's [recovery workflow documentation](https://github.com/rear/rear/blob/master/doc/user-guide/09-design-concepts.md), ReaR verifies the recovery information and available hardware, recreates the filesystem layout, restores the protected files into that layout, and finally leaves the recovered system in a state from which it can boot again.

This is what makes ReaR different from an ordinary filesystem backup. Having copies of `/etc`, installed packages and application files is useful, but those copies alone do not recreate the disks, RAID arrays, filesystems, mount points and boot environment needed to run them. ReaR bridges that gap between *having the files* and *having a working machine again*.

#### How it is used here

For this server, ReaR is the **operating-system and bare-metal recovery layer** of the wider backup strategy, configured to produce a bootable ISO and a filesystem backup using `NETFS` with `tar`. Both are written to the remote NFS backup storage rather than being left only on the server they are intended to recover.

The resulting ReaR set includes the bootable recovery image, the compressed filesystem backup, recovery metadata and logs. The procedure also records additional information about the running system, including installed packages, storage layout, RAID state, mounted filesystems and active services. That information is useful both for verification and for troubleshooting if a future recovery does not behave exactly as expected.

ReaR is primarily intended here for a **full system recovery**. If the server becomes unbootable, the disks have to be replaced, or the operating system has to be rebuilt from a known-good state, the recovery ISO provides the starting point for recreating the machine.

That does not mean ReaR is the preferred tool for every restore. Its `NETFS` backup is archive-based, so individual files can potentially be extracted if necessary, and ReaR itself provides workflows such as `mountonly` and `restoreonly`. But rebuilding the entire machine because one configuration file has been deleted would make little sense. Smaller recovery jobs are handled by the more appropriate backup for that particular component.

The ReaR backup is also deliberately **not a complete copy of the server**. Large data areas that have their own recovery strategies are excluded, including the live MariaDB data, Docker data, local database backups and the `/restore` area. Those components are restored separately after ReaR has returned the host itself to a usable state.

The recovery sequence therefore looks broadly like this:

```text
ReaR rescue environment
        ↓
Recreate disks, RAID, filesystems and mounts
        ↓
Restore the protected operating-system files
        ↓
Return the host to a bootable, configured state
        ↓
Restore databases, Docker and application data separately
```

#### What it protects

ReaR protects the **host operating environment** rather than the high-volume application data.

That includes the AlmaLinux installation, installed packages, system configuration, users and groups, permissions, scheduled jobs, service definitions, networking and firewall configuration, and the host-level software required by the applications.

It also protects the configuration for services such as Apache, PHP, MariaDB, Docker, Webmin and Virtualmin. The important distinction is that it protects the **MariaDB server software and configuration**, for example, but not the hundreds of gigabytes of live database files under `/var/lib/mysql`. In the same way, it protects the Docker engine and host-side configuration without attempting to carry the entire `/var/lib/docker` tree.

The storage layout is also part of what ReaR preserves. That matters on this machine because `/`, `/boot` and `/var/lib` are not simply directories inside one filesystem. They are backed by separate RAID1 arrangements and filesystems that have to be recreated correctly before the remaining data can be put back.

#### Why ReaR was chosen

There are many ways to copy the files from a Linux server, but copying files is only part of a bare-metal recovery.

Without a tool such as ReaR, a total-loss recovery would begin with manually reinstalling AlmaLinux, recreating the RAID arrays and filesystems, restoring mount points, reinstalling packages, rebuilding the boot environment, recreating users and permissions, restoring system configuration and enabling services. Only after all of that had been completed could the application data itself begin to be restored.

Even after all of that work, however, the result may still be little more than a basic working installation. Updates may still need to be applied, specific package or runtime versions installed, and smaller configuration differences resolved before the server truly matches the production environment it replaces. None of this is impossible, but every additional manual step adds time to a recovery process whose main objective is to get the system back online as quickly as possible.

ReaR turns much of that work into a repeatable recovery procedure.

It also fits the hybrid nature of this backup strategy particularly well. ReaR does not have to carry the hundreds of gigabytes of database and Docker data because those components already have their own recovery paths, and by excluding them, ReaR can concentrate on the part it is particularly well suited to restoring: the underlying Linux host and the environment on which everything else depends.

ReaR was therefore chosen not because it solves every part of the recovery problem, but because it solves one particularly difficult part very well — returning the bare-metal machine to a bootable, correctly configured state on which the remaining application and data layers can then be restored.

### Using the existing database backups

The production database backups are generated and managed by in-house scripts, so their complete source is not reproduced here. The following sections describe their operation, backup structure, retention policy and restore implications in enough detail to explain and evaluate the recovery strategy.

#### How the backups run

The database backups are logical backups created with `mariadb-dump`. They run automatically on a schedule (cron job) and, under normal circumstances, require no manual intervention.

The output from `mariadb-dump` is streamed directly through compression rather than first being written as a complete uncompressed SQL file. That keeps the temporary disk-space requirement low and produces compressed backup files that are easier to store and transfer.

The scripts use strict shell error handling so that failures in the dump or compression pipeline are not silently ignored. Backup output is also checked after creation, including verification that the compressed files can be read successfully, and while that does not prove that a database can be fully restored — only an actual restore test can do that — it does catch obvious failures such as incomplete or corrupt compressed output.

#### Breaking up the large tables

The larger databases are not backed up as one monolithic file.

The schema is dumped separately from the data, ordinary tables are grouped together, and the very large tables are handled independently. This makes both the backup and the eventual restore easier to manage.

For the `metrics` database, the backup is divided broadly into:

- the database schema;
- the ordinary tables;
- the large `demand` table;
- the much larger `daily_requests` table.

The `daily_requests` table contains more than 660 million rows, so treating it as one backup unit would create an unnecessarily large restore job. Instead, it is divided into monthly dumps using its indexed request date.

That has two advantages. First, a failed restore does not mean restarting the import of the entire table from the beginning. Second, the monthly files can be restored in whatever order is most useful.

The `datasphere` database follows the same general idea. Its schema is backed up separately, most tables are grouped together, while the larger tables are dumped individually.

The result is still a logical backup of each database, but it is divided into units that are easier to handle, verify and restore.

#### Seven recovery points

The scripts maintain a seven-day rolling rotation.

Each day of the week has its own backup set, giving seven discrete recovery points rather than continually overwriting the only available copy. When the same weekday comes around again, the previous set for that day is replaced by the new one.

This is not point-in-time recovery. It does, however, provide a useful window if a problem is discovered after the fact. If bad data, corruption or an application error is noticed several days after it occurred, there may still be an earlier daily backup from before the problem was introduced.

The tradeoff is storage. Keeping seven logical backup sets consumes more space than keeping only the most recent copy, but it provides a much more useful recovery window without the storage requirement of retaining seven complete physical database backups.

#### Local and remote copies

The rolling backups are created locally under `/var/lib/backups`.

That makes them immediately available for routine recovery work, but by itself it is not sufficient protection against total server loss. `/var/lib/backups` resides on the same physical machine as the databases it protects, so a catastrophic failure that removes the server also removes those local copies.

The disaster-recovery strategy therefore treats the local backup as the first copy, not the final destination, and the selected backup sets are also copied to the remote backup storage so that the database recovery points survive the loss of the machine itself.

This is an example of strengthening an existing process rather than replacing it while the logical backup scripts already work and already divide the databases in a way that suits recovery. The wider disaster-recovery design simply adds the off-server protection they need.

#### Restoring the newest data first

The way the backups are divided also defines the way they can be restored.

The schema is restored first so that the tables and database structure exist before data is imported. The ordinary tables can then be restored, followed by the larger tables that have been separated into their own backup files.

The monthly `daily_requests` dumps provide an additional advantage. The newest month can be restored first, followed by progressively older months. That matters because a full import of hundreds of millions of rows can take a considerable amount of time. If the application depends most heavily on recent data, restoring the newest periods first can return the most useful part of the service while the older historical data continues to be imported in the background.

The backup structure therefore does more than make the files easier to handle. It becomes part of the recovery strategy itself.

#### Why keep the existing logical backups?

A physical backup created with `mariadb-backup` could provide a faster full-database restore, and it remains a valid option for future development of the system. But replacing the existing logical backup process immediately would also introduce a new backup method, different storage requirements and a more complicated retention strategy.

The existing scripts are already operating, already provide seven daily recovery points, and already divide the largest tables into manageable restore units. They are also portable and easy to inspect, and their compressed output fits naturally into the available remote-storage strategy.

Keeping them therefore follows the same modular principle as the rest of the recovery design: retain a component that already works, strengthen the part that is missing, and avoid redesigning unrelated parts of the system without a clear reason.

If the database recovery requirements change later — for example, if restore time becomes more important than storage efficiency — the database backup method can be replaced or supplemented without changing the operating-system, Docker or file-backup procedures around it.
