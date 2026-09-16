## Lay of the land

The server used for this case study is not a typical website-hosting server. It does host a couple of websites, but its main role is to run a number of web applications that are continually being developed and updated.

Those applications depend on large MariaDB databases that continue to grow as new data is collected every day, and several of them run inside Docker containers so that different runtime requirements can be kept separate. The result is a production system whose state is spread across the operating system, application files, database data, container environments and a large amount of supporting configuration.

The storage layout reflects that workload.

The server has four NVMe drives arranged as two separate RAID1 groups:

```text
Bare-metal server
│
├── 2 × 894.3 GB NVMe
│   ├── RAID1 /boot       ~1 GB
│   └── RAID1 /           ~892 GB
│
└── 2 × 1.7 TB NVMe
    └── RAID1 /var/lib    ~1.8 TB
```

The system drives contain the operating system, `/boot`, application files, user data and the normal Linux filesystem hierarchy. The second pair of drives is dedicated to `/var/lib`, which contains the large and fast-growing parts of the system, including MariaDB, Docker and local backup data.

At the time of writing, the main filesystems look like this:

| Filesystem | Size | Used | Free |
| --- | ---: | ---: | ---: |
| `/` | 892 GB | 377 GB | 515 GB |
| `/var/lib` | 1.8 TB | 1.1 TB | 669 GB |

Some of the larger directories are:

| Directory | Approximate size |
| --- | ---: |
| `/var/lib/mysql` | 732 GB |
| `/var/lib/docker` | 436 GB |
| `/var/lib/backups` | 69 GB |
| `/home` | 275 GB |
| `/restore` | 80 GB |

The separate `/var/lib` filesystem was not created for this backup project. It is part of the server's existing design.

There are two main reasons for keeping it separate. The first is capacity. The databases and Docker data grow much faster than the operating system, so placing them on their own storage allows that part of the server to expand independently.

The second is failure containment. If a large database or container workload fills `/var/lib`, it does not automatically consume all the free space on the root filesystem as well. The applications may still fail because their data volume is full, but the operating system is less likely to be taken down with them.

All of the main storage is mirrored with software RAID1. That protects the server against the failure of a single member disk, but RAID is not a backup. It does nothing to help if a file is deleted, a database is corrupted, an application writes bad data, both members of an array are lost, or the entire server becomes unavailable.

The backup destination creates another constraint.

The hosting provider supplies remote storage that is independent of the local disks and can be mounted over NFS or accessed through FTP. The server currently has 500 GB of that storage available, and for this recovery plan it will be expanded to 1 TB.

That is still smaller than the amount of data that would have to be protected if we simply tried to copy the server as one large block. `/var/lib` alone currently holds around 1.1 TB of used data, before we include the hundreds of gigabytes already consumed on `/`.

And that is before considering that the largest parts of the server are not static. The databases continue to grow every day, Docker continues to accumulate images and build data, and the applications themselves continue to change as they are developed.

A straightforward full copy of everything would therefore be both inefficient and difficult to fit within the available remote storage.

More importantly, not everything on the server needs to be backed up or recovered in the same way.

The operating system has one set of recovery requirements. The databases have another. Docker presents a different problem again, and some of the raw application data can actually be used to rebuild database content from scratch.

Before deciding how to protect the server, we therefore need to break it into its individual parts and understand what each one really needs in order to recover.
