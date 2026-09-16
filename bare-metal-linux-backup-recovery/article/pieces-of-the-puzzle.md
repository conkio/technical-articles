## Pieces of the puzzle

A server is made up of separate, distinct components — each with its own set of problems and requirements. Those components can fail in different ways, each one can require a different strategy when it comes to that all-important process of backup and restore, and together they can make recovery a real headache, especially in the rare case of a full system recovery.

In the simplest case, a configuration file may have been overwritten or become corrupted after an update. A backup copy allows the user to restore it back to a prior working condition. But a corrupted table in a database is not so straightforward to fix. You cannot safely treat a table like an ordinary file and simply drop in an older copy. Depending on the structure of the database, there may be foreign key constraints or IDs referenced by other tables that did not exist in the older version. Restoring one table without understanding those relationships can create inconsistencies elsewhere and leave the database out of sync.

An even worse case is operating system failure. Some errors may still be recoverable, but a complete OS collapse usually means rebuilding the machine from scratch unless a proper recovery procedure has already been put in place. This level of OS collapse could be due to a disk failure, an upgrade that didn't complete properly, or not uncommonly, human error such as bad settings in vital configuration files, a misbehaving script that wasn't properly tested, or as simple as the deletion of crucial files.

So before deciding how to back up the server, we need to fully examine and understand what each piece actually represents and the best backup and restore strategy for that case.
