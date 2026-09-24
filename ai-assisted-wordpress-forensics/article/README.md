# Building a Read-Only AI Investigator from a Real-World WordPress Compromise

Occasionally, I get cries for help from clients and friends whose websites have been hacked or otherwise compromised, almost all of them involving WordPress sites. Usually, by the time the incident is detected—or, even worse, by the time someone finally asks for help—the damage has already spread well beyond a salvageable state.

I’ve been giving a lot of thought to how best to approach these types of incidents, and it occurred to me: **“Could an AI agent be used to establish whether a site has been compromised, and investigate the evidence effectively?”**

A forensic investigation can require broad access, but I don’t want to give the agent more capability than it actually needs. The aim is to expose enough evidence for it to investigate effectively while keeping the boundaries deliberately narrow. I also want to know whether the same approach could eventually work beyond a single WordPress compromise.

A few weeks ago, one such case landed in my lap. This was not a test site seeded with a few obvious `eval()` calls to see whether an AI would spot them. It was an actual WordPress installation from a real incident, with no planted indicators and no predetermined list of malicious files for the agent to recover.

Rather than build a malware scanner and call an LLM at the end, I decided to turn the incident into an experiment. I would give the model a small set of purpose-built, read-only forensic tools, let deterministic code establish facts such as hashes and file comparisons, and leave the model to decide which evidence mattered and what it wanted to investigate next.

If the investigation confirmed that the site was compromised, the safest course of action would be to rebuild from known-good sources.

This is Part 1 of a three-part experiment. Here I use the original compromised site to develop the investigator; Part 2 will test the same tooling against a clean site, and Part 3 against a different compromise it was not designed around.

Throughout this article, **model** refers to the LLM itself: the part that reasons about the evidence and decides what to investigate next. **Agent** refers to the complete system around it: the model, its tools, the control loop, and the restrictions governing what it is allowed to do.

## The case

The site in question was a WordPress multisite installation. There were seven days of rolling backups available, which sounds reassuring, but by the time the problem was noticed, the compromise had already made its way into all seven backups.

At that point the backups were still useful as evidence, but not as a trusted recovery point. For this experiment, that was enough: repairing the site would come later.

The starting point was a compressed archive of the site taken from one of those backups. I treated the contents of that archive as hostile from the outset. Nothing inside it needed to be executed in order to investigate it, and I saw no reason to give either myself or the agent an opportunity to do so, intentionally or accidentally.

The analysis environment was therefore kept deliberately simple: no web server, no PHP runtime serving the site, no database connection, no attempt to launch WordPress. The compromised files were the evidence, not the application.

Everything would be examined statically.

There was another reason for doing it this way. If the eventual tool was going to be useful to someone who wasn't a WordPress security specialist, I didn't want its safety to depend entirely on whether the operator knew which commands were or weren’t dangerous. Any restrictions needed to exist in the tooling itself.

So I set the boundaries early on. The agent could inspect evidence, but it could not modify it; it could calculate hashes, compare files, examine metadata and read controlled portions of files, but it could not execute code, delete anything, repair anything or invoke an unrestricted shell.

This was not meant to be an autonomous incident-response system. Its job was solely to investigate and answer one question: was the site compromised?

## Establishing some ground truth

Before involving an LLM, I needed a layer of deterministic evidence.

This is an important part of the design, because there are some questions that an AI model should not have to “reason” about at all. Two files either have the same SHA-256[^1] hash or they don't. A file either exists in the official WordPress distribution or it doesn't. If a reference file contains 405 bytes and the version on the affected site contains 36,575 bytes, that should come from code, not from a language model estimating what it has seen.

The first tool simply inventoried the backup archive without extracting it, which gave me a picture of what was actually inside: file counts, directory counts, file extensions, approximate size, suspicious archive paths and other basic characteristics. It also gave me a way to look at a very large site without immediately dumping thousands of filenames into an AI prompt.

The archive contained more than 139,000 files, with over 111,000 of them under the uploads area alone. That isn’t especially surprising for a large multisite, but it immediately illustrates one of the problems with the naive approach. Asking an LLM to “look through the site” is not especially useful when the site contains that many files. Some form of reduction has to happen first.

The next deterministic step was more useful. With the WordPress version identified statically, I downloaded the corresponding official WordPress distribution and used it as a reference, comparing the site's WordPress core files against that reference by SHA-256.

The comparison separated the results into several categories: files identical to the official distribution, files that differed, official files that were missing, and files present inside core-controlled directories that did not exist in the reference distribution.

Site-specific files such as `wp-config.php` and `.htaccess` were treated separately. Their presence is perfectly normal, but their contents may still matter during an investigation.

The archive inventory covered the entire site, including `wp-content`, but the clean-reference comparison was deliberately limited to WordPress core. Some plugins and themes could in principle be checked against their published releases, while premium or custom code may not have an independently obtainable reference, and uploads are site-specific by nature. In this experiment, `wp-content` remained part of the inventory and could still produce leads for later inspection, but it was not subjected to the same deterministic reference comparison as WordPress core.

The comparison produced a much smaller and far more interesting set of evidence. Out of 3,338 reference WordPress files, 3,337 were identical and none were missing. One was different: `index.php`, which was 36,575 bytes on the affected site rather than the 405 bytes in the official distribution.

There were also numerous PHP files inside areas of WordPress core where the official distribution had no corresponding files. Some had innocuous-looking names. Others were hidden files. Several appeared repeatedly in different directories.

At this point I already had strong evidence that something was wrong, but again, that wasn't really the experiment.

A conventional script had surfaced anomalies because I had explicitly used it to compare the site against a known reference. The script could tell me where the filesystem differed from a clean reference, but it did not decide which anomalies deserved follow-up, combine those observations into an investigation, or choose what evidence to inspect next.

The more interesting question was what an AI model would do once it had to make those decisions for itself.

That became the baseline test.

[^1]: **Why SHA-256?** The hash acts as a fingerprint of a file’s contents, independent of its filename or location. Two files with the same name can have different hashes, while files with different names or paths can have the same hash if their contents are identical. File size alone is not sufficient, because two files can be the same size while containing different data. Here, SHA-256 was used both to compare WordPress core files against the official distribution and to identify exact duplicate payloads across the site.

## Baseline: reports only

For the first test, I deliberately kept things simple.

The model was given the reports produced by the deterministic scripts: the archive inventory, the WordPress core comparison and the various lists of files that had been flagged for attention. It could read the evidence, but it had no way to inspect the underlying files itself.

In other words, this wasn't really an agent yet. It was an LLM being asked to perform triage from a fixed set of reports.

The result was encouraging. It immediately focused on the modified `index.php`, the unexpected PHP files inside `wp-admin` and `wp-includes`, the suspicious files in the site root, and site-specific files such as `wp-config.php` and `.htaccess` that warranted closer inspection. That was broadly the direction I would have taken manually. But it also made an important mistake.

One of the deterministic reports showed that there were 48 unexpected PHP files. Separately, a number of suspicious files were 3,700 bytes in size and appeared to share characteristics.

The model joined those two observations together and reported that at least 48 unexpected PHP files were 3,700 bytes and shared the same hash.

**The reports did not actually establish that.**

It was a plausible guess, and as it turned out there really was a large group of identical files, but the model had promoted an inference into a fact.

This was precisely the kind of question the deterministic layer existed to answer, and the model had answered it without calculating anything.

The baseline had done two useful things. It had shown that the model was capable of prioritising the right areas of a large and noisy dataset, but it had also exposed the limitation of asking it to work entirely from pre-generated reports. If it wanted to answer a follow-up question, it had no way of gathering the evidence needed to answer it.

That led to the first proper agent.

## V1: let the agent investigate

The next step was to provide the model with an initial minimal forensic toolbox.

I did not want to give it shell access. Instead, I exposed two purpose-built read-only functions:

- `inspect_file(path)`
- `find_same_hash(path)`

`inspect_file()` allowed the agent to request information about a specific file. It returned filesystem metadata, a SHA-256 hash and a static content preview capped at 64 KiB. Smaller text files could therefore be returned in full, while larger files were truncated.

Because anything returned by a tool would enter the model's context, sensitive values had to be removed before that happened. For `wp-config.php`, the tool redacted the database connection values together with the WordPress authentication keys and salts before returning the preview. The redaction was deliberately heuristic rather than foolproof: it reduced the risk of exposing obvious secrets, but it was not a guarantee that every possible secret would be detected.

I also set `store=False` on the Responses API requests, so I was not asking the API to persist the response objects for later retrieval. That was a data-handling choice rather than a model setting.

`find_same_hash()` answered a much narrower question: given a file, how many files in the working copy had exactly the same SHA-256 hash?

That second tool was partly a response to the mistake in the baseline run. `inspect_file()` already gave the model a SHA-256 hash for each file it examined, so it could establish that individually inspected files were identical. What it could not do efficiently was determine how many copies of a given payload existed across the entire working copy. `find_same_hash()` turned that into a single deterministic query.

There were restrictions around the tools as well: paths were confined to the extracted working copy, attempts to traverse outside that directory were rejected, and symbolic links were not followed into arbitrary parts of the system.

The agent itself was a small Python control loop built around OpenAI's Responses API, using `gpt-5.6-luna`. Each request sent the model the investigation instructions, the evidence accumulated so far and schemas describing the forensic functions it was allowed to call. If the model returned a function call, the local Python dispatcher executed the corresponding read-only tool, added its result back to the conversation, and sent the updated evidence to the model for the next round.

Because `store=False` meant the client was maintaining the conversation state itself, the complete model output also had to be carried into the next request, including the function-call and reasoning items. The loop continued until the model returned a final assessment rather than another tool request.

This is the core of the actual V1 loop, trimmed for readability:

```python
for round_number in range(1, MAX_TOOL_ROUNDS + 1):
    response = client.responses.create(
        model=MODEL,
        instructions=INSTRUCTIONS,
        tools=TOOLS,
        input=input_items,
        store=False,
    )

    response_items = [
        jsonable_output_item(item)
        for item in response.output
    ]
    input_items.extend(response_items)

    calls = [
        item
        for item in response.output
        if item.type == "function_call"
    ]

    if not calls:
        final_text = response.output_text
        break

    for call in calls:
        arguments = json.loads(call.arguments)
        result = call_local_tool(
            call.name,
            arguments,
        )

        input_items.append(
            {
                "type": "function_call_output",
                "call_id": call.call_id,
                "output": json.dumps(result),
            }
        )
```

*Trimmed from the V1 investigator control loop.*

The important point is that the model never had direct filesystem or shell access. It could only request one of the functions I had explicitly exposed; the local Python code decided what actually ran and returned the result.

For reproducibility, V1 capped the investigation at 12 model rounds. The source did not explicitly set temperature or reasoning effort, nor did V1 disable parallel tool calls. The latter would change in V2.

The original read-only restrictions remained in place. What changed was that the agent could now choose its own investigation path.

The initial reports were still the starting point, but the model could decide that `index.php` looked interesting and inspect it. It could then move on to a hidden PHP file, compare its hash against the rest of the site, inspect another suspicious file and continue building its case.

This was much closer to the experiment I actually wanted to run.

### Correcting the first mistake

One of the first useful results came from the 3,700-byte PHP files. The agent inspected `.public.php` and then called `find_same_hash()`.

This time there was no inference involved: the tool established that **43 files across the site had exactly the same SHA-256 hash**. Of the 48 unexpected PHP files identified by the earlier core comparison, **42 belonged to this exact hash group**; one further file in the group was under `wp-content`.

The baseline had effectively turned “48 unexpected PHP files” into “48 copies of the same file.” The evidence showed something different. It’s a small numerical difference, but a significant methodological one.

### Following the evidence

The agent continued through the files it considered most relevant. The modified `index.php` contained encoded and dynamically evaluated PHP, while other unexpected files contained similar obfuscation and execution behaviour.

One root-level file, `ai.php`, exposed file-management functionality characteristic of a web shell. There were also other files, including `ammika.php`, `saiga.php` and unexpected PHP files inside `wp-includes`, that contained encoded execution logic.

At this point the question of whether the site had been compromised was no longer particularly ambiguous. The important part, however, was how the agent had arrived there. The deterministic tools had not been programmed with a list saying: inspect `ai.php`, then inspect `ammika.php`, then inspect `saiga.php`.

The tools established facts when asked; the model decided which files were worth investigating next.

### Where V1 fell short

V1 had three weaknesses.

`inspect_file()` was still too generous. A 64 KiB preview of a heavily obfuscated file could consume many thousands of tokens without adding much useful information.

More importantly, I was treating the contents of compromised files as data, but from the model’s point of view they were still text. That created an additional trust problem: prompt injection.

The term is analogous to SQL injection, where an application mistakenly allows untrusted user input to become part of an executable SQL statement. The mechanisms are different, but the underlying mistake is similar: data from an untrusted source must not be allowed to cross a trust boundary and acquire authority it was never meant to have.

A compromised file could contain ordinary source code, malicious code, or text deliberately written to influence an AI investigator. Whether planted on purpose or simply phrased that way by coincidence, evidence from a hostile system should remain evidence, never instructions.

There was also a problem with the metadata itself. Because I was working from an extracted copy of the site, timestamps, ownership and permissions could have changed during backup, transfer or extraction. I needed to make sure the agent did not mistake those values for authoritative metadata from the original production system.

V1 was useful, but its tools were returning too much raw content and not enough context about what could actually be trusted.

That became V2.

## V2: redesigning the tool boundary

The API loop itself stayed essentially the same in V2. What changed was the contract between the model and its tools, and the dispatcher that enforced it.

The problem was not that the model needed more access. If anything, it needed less raw access and better-structured information. I split `inspect_file()`’s responsibilities across separate tools.

The first, `analyze_file(path)`, performed deterministic static analysis and returned structured findings rather than raw file contents. It could report the file’s size and hash, identify potentially interesting PHP functions, detect signs of obfuscation, extract URLs and flag other characteristics that might warrant investigation.

```json
{
  "path": "index.php",
  "size": 36575,
  "executed": false,
  "raw_content_returned": false,
  "indicators": {
    "dynamic_execution": {
      "eval": {
        "count": 3
      }
    },
    "encoding_compression": {
      "base64_decode": {
        "count": 2
      }
    }
  },
  "obfuscation_signals": {
    "base64_like_blob_count": 3,
    "largest_base64_like_blob": 35684
  }
}
```

*Trimmed `analyze_file()` result for `index.php`.*

The structured result deliberately did not return the file itself. That reduced the amount of attacker-controlled text entering the model’s context, although it did not eliminate it entirely: derived values such as extracted URLs could still originate from hostile input.

If the model decided that it genuinely needed to inspect a file’s contents, it had to make a separate request using `read_file_region(path, start, end)`. A request could cover at most 80 lines, and the returned content was capped at 16 KiB.

There was also an escalation gate. The agent could not request raw content from a file until it had first called `analyze_file()` on that same file during the current investigation. The intended path was simple: **structured evidence first; raw evidence only when necessary.**

```python
if name == "analyze_file":
    result = analyze_file(
        arguments["path"],
        root=DEFAULT_SITE_ROOT,
    )
    analyzed_paths.add(
        result["path"]
    )
    return result

# ...

if name == "read_file_region":
    canonical = canonical_agent_path(
        arguments["path"],
        root=DEFAULT_SITE_ROOT,
    )

    if canonical not in analyzed_paths:
        return {
            "error": "EvidenceEscalationDenied",
            "message": (
                "This file must first be examined "
                "with analyze_file before raw-region "
                "inspection is permitted."
            ),
        }
```

This was not merely a prompt instruction. `analyze_file()` returned a canonical path, and raw-read requests were canonicalised before being checked against the set of files already analysed. If the model tried to skip the analysis stage and go straight to the contents, the dispatcher refused the request.

I also disabled parallel tool calls in V2. That meant the model could not request `analyze_file()` and `read_file_region()` for the same file simultaneously in a single turn. The analysis result had to be processed first, and any raw read had to arrive as a later request. Apart from making the escalation gate easier to reason about, this made the investigation sequence more explicit in the transcript.

Raw content returned by `read_file_region()` was explicitly labelled as **untrusted forensic evidence**, with an instruction that anything inside it must be treated as evidence rather than as authority. Labelling alone cannot prevent prompt injection, but the surrounding architecture limited what a manipulated model could do: the available tools remained read-only, filesystem access remained confined to the working copy, and the evidence could not be executed or modified. A successful manipulation could still misdirect the investigation or cause unnecessary evidence to be examined, so the trust boundary reduced the risk rather than eliminating it.

I also made the source of filesystem metadata explicit. Values such as timestamps, ownership and permissions were labelled as belonging to the **lab-extracted working copy**, with a warning that they should not be treated as authoritative metadata from the original production server.

The aim of V2 was not to make the model smarter. It was to make the boundary between the model and the evidence more precise.

The first run provided a useful demonstration of those boundaries in action. At one point, the model asked for 120 lines from `ai.php`. The tool refused the request because a single read could cover no more than 80 lines.

The limit itself was enforced in `forensic_tools_v2.py`:

```python
MAX_REGION_LINES = 80
MAX_REGION_BYTES = 16 * 1024

# ...

if (
    end_line - start_line + 1
    > MAX_REGION_LINES
):
    raise ForensicToolError(
        f"At most {MAX_REGION_LINES} lines "
        "may be requested at once."
    )
```

The model then adjusted its request rather than being granted an exception:

```text
Agent → read_file_region("ai.php", 1, 120)
Tool  → ForensicToolError: At most 80 lines may be requested at once.

Agent → read_file_region("ai.php", 1, 80)
Tool  → Success: 80 lines returned.
```

*Trimmed transcript from the V2 first run.*

That may sound like a small detail, but I think it is one of the strongest examples in the experiment. The model did not merely receive a prompt telling it to “be careful.” It encountered a hard limit imposed by the system and adapted its investigation around it.

### What V2 found

With those changes in place, I ran the V2 agent against the same evidence. The investigation took 17 model rounds and 16 tool calls. Starting from the same reports but without V1’s conclusions, V2 independently revisited several of the files that V1 had investigated, including `index.php`, `.public.php`, `ai.php`, `ammika.php` and `saiga.php`.

The modified `index.php` was an obvious place to start. The official WordPress version was only 405 bytes, while the copy from the affected site was 36,575 bytes. Static analysis found three calls to `eval`, two to `base64_decode`, a `__halt_compiler()` marker and a 35,684-byte base64-like block. Importantly, none of that code was executed.

V2 also checked `.public.php` and independently established the same result as V1: **43 files across the WordPress installation shared exactly the same SHA-256 hash**.

Another root-level file, `ai.php`, proved even more interesting. The structured analysis showed file-manipulation functions and numerous `$_GET`, `$_POST` and `$_FILES` inputs, which was enough to justify looking at the contents.

Using the gated raw read described earlier, the permitted reads showed that `ai.php` implemented file upload, deletion, editing, renaming, directory listing and file reading. In practical terms, it was a file-management web shell.

The agent also checked `.htaccess` and `wp-config.php`, both of which had been flagged for review by the earlier deterministic analysis. `.htaccess` contained ordinary WordPress rewrite rules. Static analysis of `wp-config.php` found no `eval`, encoding, compression or obfuscation indicators, although that did not establish that its credentials or configuration values were safe.

| Evidence | Deterministic observation | What it supported |
| --- | --- | --- |
| `index.php` | 36,575 bytes vs 405-byte reference; `eval`, `base64_decode`, large encoded block | Core file had been materially altered with obfuscated executable PHP |
| `.public.php` | 43 files sharing the same SHA-256 hash | Same payload existed across multiple locations |
| `ai.php` | File upload, delete, edit, rename, list and read functionality | File-management web shell behaviour |
| `.htaccess` | Ordinary WordPress rewrite rules | Flagged for review, but not evidence of compromise |
| `wp-config.php` | No static execution, encoding, compression or obfuscation indicators | Review did not produce additional evidence of compromise |

The agent examined several other unexpected PHP files, including `ammika.php`, `saiga.php`, `wp-includes/customize/nav.php`, `wp-includes/html-api/decoder.php` and the much larger `wp-includes/html-api/foot.php`. Static analysis found various combinations of encoded or compressed data and dynamic execution functions in these files. `foot.php` alone was 963,133 bytes, exactly the sort of file where blindly feeding the entire contents into an LLM would have been both wasteful and unnecessary.

Not everything inspected was suspicious. `.htaccess` and `wp-config.php` produced no additional evidence of compromise, and V1 had also found application-specific files under `wp-content` that were consistent with legitimate plugins. The agent did not automatically classify every unusual PHP file as malware. That mattered because a useful forensic investigator has to be capable of ruling evidence out as well as flagging it.

By the end of the run, the agent had enough evidence to answer the original question with high confidence: the site was compromised, but more importantly, it could explain why.

There was a modified official WordPress core file containing heavily obfuscated dynamic PHP execution, a 43-file group sharing the same obfuscated PHP payload, a file-management web shell, and additional unexpected PHP files containing encoded or dynamically executed content. At the same time, the agent stopped short of claiming things the evidence could not establish. It could not prove that any specific file had actually been executed, identify the original entry point, determine who the attacker was, or say what changes might have existed in the WordPress database.

That last part is important. The objective was never to get the AI to produce the most alarming malware report possible. It was to see whether it could distinguish between **what the evidence established, what it merely suggested, and what remained unknown**.

At that point, trying to find and delete every suspicious file would have been playing with fire. One overlooked backdoor or persistence mechanism could be enough to let an attacker straight back in. Once compromise had been established, the appropriate recovery path was to rebuild from known-good sources. With all seven rolling backups affected, that meant rebuilding from clean sources rather than restoring one of those backups.

## What actually improved?

| Stage | What the model could access | What changed | Main limitation |
| --- | --- | --- | --- |
| **Baseline** | Pre-generated reports only | Could prioritise suspicious evidence | Could not gather new evidence; made the 48-file inference |
| **V1** | Reports + `inspect_file()` + `find_same_hash()` | Could investigate files and verify exact duplicates | Raw file content was exposed too readily |
| **V2** | Structured analysis + gated raw reads + hash search | Evidence exposure became controlled and explicit | Still a single case; generalisation unproven |

At first glance, the progression from the baseline to V1 and then V2 might look like a story about giving an AI more tools, but I came away with almost the opposite conclusion: the biggest improvement came from giving the model **better-defined tools and less ambiguous access to the evidence**.

The report-only baseline was already capable of spotting the important anomalies. Its weakness was that, when the available reports did not answer a question, it could fill the gap with a plausible inference—as it did when it effectively treated the 48 unexpected PHP files as members of the same repeated payload group.

V1 solved part of that problem by allowing the agent to gather evidence for itself. It could inspect files, calculate hashes and establish that **43 files shared the same payload**.

V2 tightened the boundary further. Structured analysis came before raw content. Raw reads had to be justified by a previous analysis. Read sizes were capped in code. Compromised file contents were explicitly treated as untrusted evidence. The model was still doing the interesting part: deciding which evidence mattered and what question to ask next.

But whenever a question had a deterministic answer, the tooling was responsible for establishing the fact. That, more than anything else, became the design principle I took away from the experiment:

**Let the model decide what to investigate. Let deterministic tools decide what is true.**

## What this experiment does not prove

There is an obvious problem with drawing too broad a conclusion from this experiment: I built the tooling while investigating this particular compromise.

The model was not told where the malicious files were or what conclusions it should reach, but chose which evidence to pursue and, once given the appropriate tools, established the findings for itself.

However, the **tooling itself was not developed blind**. As I learned more about the incident, I changed the way evidence was presented to the model. The WordPress core comparison became an important source of leads and `find_same_hash()` was added after the baseline exposed the need for a reliable way to establish repeated payloads. V2 was then designed around weaknesses I had observed in V1.

That is exactly how software normally evolves, but it creates a potential bias in an experiment like this. I now had an agent that could investigate **this** compromise effectively, but that did not necessarily mean I had built a general-purpose WordPress forensic investigator.

There are plenty of compromises that might look nothing like this one. An attacker could modify a legitimate plugin rather than placing obviously unexpected files inside WordPress core. Persistence might exist entirely in the database. A compromised administrator account might leave the filesystem untouched. Malicious scheduled tasks or server-level changes could sit outside the WordPress directory altogether.

None of those possibilities invalidate what the agent found here. They simply define the boundary of what this particular experiment established.

There was another limitation: the agent was analysing a static archive, not a live server. That was deliberate and, from a safety perspective, preferable for this experiment. But it meant that there were things it could not observe—running processes, network activity, database state, web-server configuration outside the archive, or what an attacker may have done before the backup was taken. Working from the filesystem alone also meant it could not reconstruct how the attacker originally gained access.

The prompt-injection boundary was likewise a design defence rather than a demonstrated one. V2 labelled raw content as untrusted evidence and constrained what the model could do with it, but this run did not contain a deliberately planted prompt-injection attempt. The experiment therefore does not prove that the agent would resist every adversarial instruction embedded in compromised content.

There is also a repeatability limitation. Each stage described here was a single preserved run. I did not repeat the same experiment enough times to measure how consistently the model would choose the same investigation path or reach the same conclusions from the same evidence.

What Part 1 demonstrated was narrower:

**Given a real compromised WordPress filesystem, could a constrained AI agent use deterministic forensic tools to gather enough evidence to establish that the site had been compromised?**

In this case, yes.

The harder question is whether the same tooling works when I do **not** already know what the answer should look like.

That requires a different kind of test.

## What comes next

The obvious next test is not another compromised site. It is a clean one.

For Part 2, I want to run the same V2 agent against a WordPress installation built specifically as a control. Rather than relying on a site that I merely believe to be clean, I can construct it from known sources: a fresh WordPress release together with selected plugins and themes whose provenance I can establish.

The interesting part is making that control realistic. A normal WordPress installation can contain plenty of things that look suspicious out of context: plugins with file-management functions, generated PHP, encoded assets, unusual directory structures, custom configuration files and code that legitimately handles user input. I want the control site to contain examples like these deliberately, because a useful forensic investigator needs to know when *not* to raise the alarm.

Part 2 therefore becomes a false-positive test. The question is whether the same V2 agent can examine a known control site, investigate the anomalies it finds, and avoid turning legitimate WordPress behaviour into evidence of compromise.

It also provides a controlled place to test one limitation from Part 1. I can place an instruction-like string inside the evidence and see how the frozen V2 agent handles it. That would not prove resistance to every form of prompt injection, but it would at least test the trust boundary deliberately rather than merely designing for the threat.

Part 3 is the more difficult test.

For that, I want a completely different compromised WordPress site—ideally one I have not previously investigated and whose compromise does not resemble the case used to develop V2.

This time the protocol needs to be blind. The agent should investigate the evidence before I investigate the site myself. Only after its assessment is preserved would I perform a separate manual investigation and compare the two. That reduces the chance of my own knowledge of the case influencing how the agent is run or how its findings are interpreted.

The V2 configuration should also remain frozen: the forensic tools, dispatcher, investigation instructions, model identifier and explicitly configured API settings should remain the same as those used at the end of Part 1. Any changes after that would need to be treated as a new version rather than quietly folded into the test.

That is the point at which the experiment stops asking, “Can this agent investigate the case it grew up around?” and starts asking the question I was interested in from the beginning:

**Did I build a useful forensic investigator for WordPress, or merely a very good investigator for one particular compromise?**

## Conclusion

The most useful lesson from this experiment was not that an AI model could spot suspicious PHP. It was that the quality of the investigation depended as much on the system around the model—its tools, constraints and trust boundaries—as on the model itself.

Each iteration reinforced the same design principle: **let the model decide what to investigate; let deterministic tools decide what is true.**

For this particular compromise, that was enough to establish the presence of malicious modification without giving the agent unrestricted shell access or allowing it to execute any of the compromised code.

It answered the question I set out with, at least for this case: an AI agent does not need unrestricted access to perform a useful forensic investigation. It needs the right evidence, the right tools, and clear boundaries around what it is allowed to trust and do.
