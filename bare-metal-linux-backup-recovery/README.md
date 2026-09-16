# From Backup to Recovery: Designing a Disaster-Recovery Strategy for a Bare-Metal Linux Server

## Table of contents

1. [Introduction](article/)
   Why backing up a production server is not the same as copying files, and why recovery time, system state, application dependencies and limited remote storage make disaster recovery a broader engineering problem.

2. [Pieces of the puzzle](article/pieces-of-the-puzzle.md)  
   Why the server cannot sensibly be treated as one backup object. This section breaks the system into recovery components and examines what each one actually requires.

   - [The operating system](the-operating-system) — Why recovering a Linux system means reconstructing more than files: storage layout, RAID, boot configuration, networking, services, users, permissions, security settings and system configuration.
   - [Databases](#databases) — The tradeoff between logical SQL dumps and physical backups with `mariadb-backup`, including restore time, storage requirements, consistency and the problems created by very large tables.
   - [Raw source data](raw-source-data) — The booking-engine JSON snapshots that feed the largest database tables, why the capture itself is time-sensitive, and why those files form an independent recovery path.
   - [Docker](#docker) — Separating persistent and difficult-to-recreate state from images, containers and hundreds of gigabytes of disposable build cache.
   - [Ordinary files](ordinary-files) — Application files, scripts, websites and user data that can be handled with more conventional filesystem backup methods.
   - [Compression](compression) — Using compression selectively to reduce storage and transfer requirements without losing sight of the CPU, working-space and restore-time tradeoffs.

3. [Lay of the land](article/lay-of-the-land.md)  
   The production server itself: its role as an application server, the RAID-backed storage layout, the separate `/var/lib` filesystem, growing MariaDB data, Docker, ordinary application data, and the mismatch between total server data and available remote backup capacity.

4. [Putting the pieces together](putting-the-pieces-together)  
   The actual recovery strategy chosen for this server, and why. Rather than replacing everything with a new backup platform, the design reuses working components where possible and adds the missing pieces needed for disaster recovery.

   - [ReaR for system recovery](rear-for-system-recovery) — Using Relax-and-Recover to capture the machine-level layout and operating-system environment and provide a bare-metal recovery path.
   - [Using the existing database backups](using-the-existing-database-backups) — Why the already-running seven-day logical backup rotation was retained initially instead of replacing it immediately with `mariadb-backup`.
   - [Breaking up the large tables](breaking-up-the-large-tables) — Dumping the 660-million-row table in monthly chunks, the 28-million-row table separately, and the remaining tables together so that long restores become restartable and manageable.
   - [Restoring the newest data first](restoring-the-newest-data-first) — Using the date-based structure of the largest table to restore recent months before older history, allowing the most useful data to become available while the full restore continues.
   - [Protecting the JSON source archive](protecting-the-json-source-archive) — Keeping recent JSON immediately accessible, compressing older data into six-month and yearly archives, and using a second server in another data centre to protect against missed API snapshots.
   - [Handling Docker selectively](handling-docker-selectively) — Preserving what is needed to return the applications to service without wasting remote capacity on rebuildable or disposable Docker data.

5. [Getting the backup off the server](getting-the-backup-off-the-server)  
   Moving the recovery data away from the hardware it protects. This section covers the provider-supplied remote storage, NFS/FTP access, the practical effect of the 1 TB capacity limit, retention, and why the first implementation uses storage that is already available rather than introducing another platform at the same time.

6. [Recovery in practice](recovery-in-practice)  
   What happens when something actually fails. The recovery path depends on the severity of the incident, from restoring an individual configuration file or database component through rescue-mode repair to a complete bare-metal rebuild.

   - [When the server still boots](when-the-server-still-boots) — The simplest recovery cases, where configuration, packages or application state can be repaired without rebuilding the system.
   - [When the OS will not boot](when-the-os-will-not-boot) — Using rescue mode, assembling RAID devices, mounting the installed system and repairing it from outside the normal boot environment.
   - [Full bare-metal recovery](full-bare-metal-recovery) — Reconstructing the server with ReaR and then restoring the database, Docker state, application data and other excluded components in the correct order.
   - [Restoring the application data](restoring-the-application-data) — Rebuilding MariaDB from the selected recovery point, using the chunked restore order, and falling back to raw JSON reconstruction where necessary.

7. [Testing the recovery plan](testing-the-recovery-plan)  
   Why producing a backup is not enough. Verification should cover archive integrity, recovery media, database dumps, restore procedures and the ability to rebuild the system in a separate environment rather than discovering problems during a real outage.

8. [Tradeoffs and next steps](tradeoffs-and-next-steps)  
   What this first implementation deliberately does not solve, and where it can be improved. Possible next steps include `mariadb-backup` for faster physical database recovery, incremental physical backups, additional automation and monitoring, and an independent off-provider copy using storage such as AWS.

9. [Conclusion](conclusion)  
   The broader lesson from the case study: disaster recovery is not about finding one backup tool. It is about understanding how the server and its applications work, deciding what each component needs in order to recover, and combining those methods into a plan that can restore useful service within realistic storage and time constraints.
