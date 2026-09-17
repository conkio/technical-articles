## Lay of the land

The server used for this case study is not a typical website-hosting server. It does host a couple of websites, but its main role is to run a number of web applications that are continually being developed and updated.

Many of those applications depend on large databases that continue to grow as new data is collected daily. Because each application has its own runtime requirements and version dependencies, it is easier to deploy them inside Docker containers where each environment can be specifically tuned. This also relieves the burden of trying to concurrently maintain several versions of Python or PHP, and their associated libraries and package managers on the host operating system. The result is a production system whose state is spread across the operating system, application files, database data, container environments, and a large amount of supporting configuration.

The machine itself is a bare-metal server running AlmaLinux 9.8. It has an AMD EPYC 4244P processor, 64 GB of memory and four NVMe drives arranged as software RAID1 pairs.

Two of the drives are approximately 1 TB each and provide the operating-system storage. The other two are approximately 2 TB each and are dedicated to `/var/lib`.

```text
Bare-metal AlmaLinux server
│
├── 2 × ~1 TB NVMe
│   ├── RAID1 /boot
│   └── RAID1 /
│
└── 2 × ~2 TB NVMe
    └── RAID1 /var/lib
```

The usable filesystem capacity is therefore roughly 2.7 TB rather than the combined raw capacity of all four drives, because each pair is mirrored. RAID1 provides redundancy against the failure of a single member of either pair, but it does not replace a backup. Accidental deletion, corruption, compromise or a mistake made by the operating system is faithfully mirrored to both drives.

The root filesystem contains the operating system itself together with the installed software and system configuration needed to run the machine. That includes Apache, PHP, the MariaDB server packages and daemon, Docker, Webmin and Virtualmin, service definitions, scheduled jobs and the configuration under `/etc`.

The high-growth application data lives elsewhere. `/var/lib` is mounted as a separate XFS filesystem on its own RAID1 array and contains the largest and most frequently changing components of the server:

| Location | Purpose | Approximate size |
| --- | --- | ---: |
| `/var/lib/mysql` | MariaDB database files | 732 GB |
| `/var/lib/docker` | Docker images, containers, volumes and build data | 436 GB |
| `/var/lib/backups` | Local backup files, including rolling database dumps | 69 GB |

The separate `/var/lib` filesystem was not created for this backup project. It already existed so that databases, Docker data and local backups could grow independently of the operating system. That also provides a degree of failure containment: if a database or container workload unexpectedly fills `/var/lib`, it does not automatically consume the remaining free space on `/` and bring the operating system down with it.

From a recovery point of view, however, the separation creates an important dependency. The applications and their data may live under `/var/lib`, but the software required to use that data lives on the root filesystem.

MariaDB is a good example. The database files themselves are under `/var/lib/mysql`, while the MariaDB daemon, libraries and configuration belong to the operating-system side of the machine. With logical SQL backups there is some flexibility because the data can be imported into a compatible MariaDB installation. A physical backup is more tightly coupled to the database engine that created it and files produced by `mariadb-backup` cannot simply be placed under an arbitrary MariaDB installation and expected to work; the restored data has to be used with a compatible MariaDB server version and storage-engine format.

Docker presents a similar split where a large part of its runtime state resides under `/var/lib/docker`, but the Docker engine itself is installed on the root filesystem. Conventional LAMP applications, on the other hand, live within the normal Apache virtual-host structure and depend directly on the PHP and other services provided by the host operating system.

The same applies to the local database backups where the seven-day rolling logical backups are stored under `/var/lib/backups`. They are valuable recovery points, but they are still on the same physical server, and if the machine is completely lost, a backup stored only there disappears with it.

That is where the remote backup storage comes in.

The hosting provider supplies 500 GB of backup space that is available independently of the server's local disks and is mounted over NFS at `/mnt/ovh-backup`, but it is planned and required to increase the allocation to 1 TB in order to accommodate a total backup setup. It is a workable storage, despite being much smaller than the roughly 2.7 TB of usable local filesystem capacity, so simply copying the entire server to the remote storage destination is not an option.

That size difference is what turns the problem from a straightforward full-copy backup into a recovery-design exercise. Some components need to be preserved almost exactly, some can be rebuilt, some compress extremely well, and some can be regenerated from other retained data.

On paper this is one server. From a recovery point of view, however, it is several interdependent storage and software layers spread across separate filesystems, with a remote backup destination considerably smaller than the combined usable capacity of the machine.
