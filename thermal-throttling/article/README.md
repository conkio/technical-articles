# Thermal Throttling: How It Works, What Causes It, and How to Prevent It

**By Constantin Kioulafas**  
*Originally written: May 2021 · Revised: August 2026*

All computer components, under normal operating conditions, generate some level of heat output that must be dissipated if the component is to continue to operate properly. When the component’s operating temperature exceeds its designed maximum operating point, it can suffer either immediate and permanent damage or reduced lifespan over the long term.

For this reason, many components adopt two methods of thermal protection: thermal throttling and thermal shutdown. Thermal throttling attempts to reduce heat output before temperatures reach a potentially damaging level, while thermal shutdown acts as a final safeguard by switching off the component or system if temperatures become dangerously high.

## Introduction

Thermal throttling is typically associated with CPUs and GPUs, yet it is not uncommon for other computer components, such as solid-state drives (SSDs), to adopt this method of self-protection, since they can also suffer from overheating.

Some SSDs incorporate a built-in thermal sensor to help monitor their operating temperature. When the drive reaches extreme temperature conditions, it uses thermal throttling in an effort to prevent damage. In the case of an SSD, this results in reduced read/write throughput.

However, as stated previously, thermal throttling is most commonly used to refer to CPU and GPU protection and will be the main focus of this article.

Processors have a maximum operating temperature specified by the manufacturer. For Intel processors, this is generally given as Tjunction Max (TJ Max), the maximum permitted temperature at the processor die. The exact value varies by model, but is often around 100°C. As the processor reaches this limit, built-in thermal controls automatically reduce its clock speed, thereby lowering performance and power consumption until the temperature returns to an acceptable level.

Reducing power consumption is generally achieved by lowering the processor’s operating frequency along with the voltage supplied to it. These values are commonly paired and adjusted together, although frequency may sometimes be limited without a corresponding voltage change. Because dynamic power consumption varies approximately with the square of voltage, the voltage reduction can account for a substantial part of the resulting power saving. Adjusting voltage and frequency while the processor is operating is known as dynamic voltage and frequency scaling (DVFS). Although thermal throttling may use DVFS to reduce heat output, the two terms are not interchangeable, since DVFS is also used during normal operation to balance performance and power consumption.

The voltage supplied to a CPU or GPU is regulated by a voltage regulator module (VRM), typically located on the motherboard or graphics card, respectively. When thermal management logic requests a lower-voltage operating state, the VRM adjusts its output to supply the corresponding voltage.

One way of reducing a processor’s operating frequency is to lower its clock multiplier. For example, with a base clock frequency of 100 MHz, a multiplier of 32 would produce an operating frequency of 3.2 GHz. Reducing the multiplier from 32 to 24 would lower the operating frequency to 2.4 GHz, representing a 25% reduction. However, the reduction applied during thermal throttling is not fixed and varies according to the processor design, temperature, power limits, and workload.

Modern computer systems and processors monitor internal temperature and workload, adjusting their performance to remain within safe operating limits. Some systems allow users to alter the operating frequency, voltage, and power limits of a CPU or GPU through the BIOS or other tuning software. Overclocking increases the operating frequency, while overvolting raises the voltage, often to support higher clock speeds.

These changes increase power consumption and heat output, making thermal throttling more likely if the cooling system cannot dissipate the additional heat. However, overclocking does not normally bypass the processor’s built-in thermal protections; thermal throttling and thermal shutdown generally remain active unless those safeguards are deliberately disabled.

## Under the Microscope (What Initiates Thermal Throttling)

Contemporary desktop processors are manufactured using process nodes such as Intel’s 14 nm process and TSMC’s 7 nm process, the latter being used for AMD’s Ryzen 5000 series. Older processors, such as the Intel Core i7-3970X, were manufactured using a 32 nm process. However, terms such as 14 nm and 7 nm identify process generations and should not be interpreted as the literal width of a transistor. Even so, transistors are now manufactured at scales where quantum-mechanical effects, including electron tunnelling, have a significant influence on processor design.

Electron tunnelling occurs when electrons pass through a barrier that, according to classical physics, they should not be able to cross. In a transistor, this can create leakage current through extremely thin insulating layers, increasing power consumption and heat output even when the transistor is not actively switching. As transistors become smaller, controlling this leakage becomes increasingly difficult and places practical limits on their design.

Heat is also produced as transistors switch between states. Each transition moves electrical charge through the processor’s circuitry and consumes a small amount of energy. Although a single transition produces very little heat, modern processors contain billions of transistors, with many transitions occurring during every clock cycle. Combined with operating frequencies measured in billions of cycles per second, the effect is considerable. For this reason, higher operating frequencies and heavier workloads generally increase power consumption and heat output.

Consider a processor that is overclocked beyond its standard operating frequency. Increasing the frequency raises dynamic power consumption, while the additional voltage often needed to keep the processor stable at higher clock speeds causes power consumption and heat output to rise even more sharply. For this reason, the increase in power consumption may be considerably greater than the percentage increase in clock speed.

Having reached a practical limit on how far clock speeds could be increased, manufacturers adopted other ways of improving processing power, such as using multiple cores and multithreading. A multi-core processor is much like having several processors in one system, except that the cores are all contained on a single physical chip.

Multi-core processors allow a computer to better cope with heavier workloads and a greater number of tasks. A game, for example, may require the processor to handle audio, physics calculations, gameplay logic and some graphics-related work. These jobs are divided into threads, which the operating system schedules across the available cores, rather than each task being permanently assigned to a particular core.

An application that makes little use of the processor will generally produce less heat than a demanding game or similar workload. If several cores are kept busy and operating at or close to their maximum frequency, power consumption and heat output will rise, and if the cooling system cannot remove this additional heat, the processor may eventually reach its maximum safe temperature, causing thermal throttling to take effect.

## Effects of Thermal Throttling

The effects of thermal throttling are not always immediately noticeable and depend on the application and system. Some of the more obvious signs that a component is running too hot or has begun to throttle are:

- an increase in fan speed, which usually means increased fan noise

- sluggish response, especially on computer systems running computationally intensive applications

- a drop in gameplay frame rate (frames per second) when the graphics card begins to throttle

In the case of GPUs, artifacts may appear in rendered scenes. Artifacts are visual impairments and can range from barely noticeable to quite severe. Although artifacts are not caused by thermal throttling itself, they can be an indication that the GPU or its video memory has become unstable. High operating temperatures are one possible cause, especially if the graphics card has been overclocked.

If high temperature is the culprit, thermal throttling may eventually kick in to protect the GPU. However, repeated artifacts should not be ignored, since other problems, such as unstable or faulty video memory, can cause them as well. Built-in thermal protections generally guard against immediate damage, but a GPU that is run persistently hot or unstable, particularly with those safeguards loosened or disabled, may suffer permanent damage over time.

## Addressing the Causes of Thermal Throttling

While several factors, either on their own or in combination, may cause a system to experience thermal throttling, correcting one or more of the factors discussed below will usually help remedy the situation.

### Clock Rate

The clock rate, or operating frequency, has a direct influence on the heat output of a processor. The higher the frequency, the more power is generally consumed and the more heat produced, especially when the increase in clock speed requires a higher voltage. Keeping the processor within its designed operating limits will reduce the likelihood of thermal throttling, although adequate cooling is still required. In fact, when thermal throttling kicks in, it lowers the clock rate in an attempt to bring the temperature back under control.

### Cooling and Airflow

Thermal Design Power (TDP), also known as the Thermal Design Point, is a value used when designing or selecting a processor’s cooling system and indicates the amount of heat the cooling system is expected to dissipate under the manufacturer’s specified operating conditions. It does not necessarily represent the processor’s maximum power consumption, since actual power use and heat output may exceed the stated TDP during boost or particularly demanding workloads.

Regardless of the type of cooling used, whether passive or active, air or liquid, it should be capable of dealing with the heat output of the processor under sustained load.

It should also be noted that good airflow through the enclosure is important, with an effective exhaust system removing hot air from inside the case while intake fans draw cooler air in, thus preventing heat from building up around the components and helping to reduce the likelihood of thermal throttling.

### Overclocking / Overvolting

Especially popular among gaming enthusiasts, overclocking involves running a CPU or GPU at a higher frequency than the standard specifications indicate, while overvolting involves increasing the voltage supplied to the component, often to keep the component stable at those higher speeds. For more extreme overclocks, this is often accompanied by replacing the stock cooling system with a more capable air or liquid cooler, although how far the cooling must be upgraded depends on how hard the component is pushed.

Excessive overclocking or overvolting can lead to instability, overheating and, in extreme cases, permanent damage, so both should be employed with caution. Higher voltage and temperature accelerate degradation mechanisms such as electromigration and dielectric wear, so an overclock that raises either will shorten the component’s lifespan to some degree. In many cases, however, the reduction is too small to matter within the useful life of the system.

### Prolonged Use

Running a system at a constantly high workload for a prolonged period allows its temperature to rise until the cooling system reaches a steady state. If the cooling system cannot dissipate heat as quickly as it is produced, the processor may reach its thermal limit, and throttling kicks in. As throttling takes effect, the temperature should level off rather than continuing to rise while the system remains in use.

Over time, dust can also build up on heatsinks, fans and other components, restricting airflow and acting as an insulator. This reduces the efficiency of the cooling system and is another factor that can lead to thermal throttling.

## Conclusion

Thermal throttling can be caused by a number of factors, such as inadequate cooling, restricted airflow, dust build-up, increased heat output from demanding workloads, or overclocking and overvolting. When a component reaches its thermal limit, throttling kicks in to reduce its operating frequency and power consumption, bringing the temperature back within its operating limits. The main distinction between thermal throttling and thermal shutdown is that throttling helps protect the component or system from damage while allowing it to remain operational.
