/* Host MMIO model for the actual clk-sdp1804-gpu.c callbacks. No hardware. */
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <errno.h>
#include <string.h>
#define __iomem
#define BIT(n) (1U << (n))
#define GFP_KERNEL 0
#define container_of(p,t,m) ((t *)((char *)(p) - offsetof(t,m)))
typedef uint32_t u32;
struct device_node { bool enabled; };
struct generic_pm_domain {
 const char *name;
 int (*power_on)(struct generic_pm_domain *);
 int (*power_off)(struct generic_pm_domain *);
};
static struct device_node child;
static u32 mmio[0x3000/4];
static unsigned int reads, writes, offsets[16];
static u32 values[16];
static u32 readl(const void *p) { reads++; return *(const u32 *)p; }
static void writel(u32 v, void *p) {
 offsets[writes] = (char *)p - (char *)mmio;
 values[writes++] = v; *(u32 *)p = v;
}
#define readl_poll_timeout(addr,val,cond,delay,timeout) \
 ((void)(delay), (void)(timeout), (val)=readl(addr), (cond) ? 0 : -ETIMEDOUT)
static struct device_node *of_get_child_by_name(struct device_node *n, const char *name)
{ (void)n; (void)name; return &child; }
static bool of_device_is_available(struct device_node *n) { return n->enabled; }
static void of_node_put(struct device_node *n) { (void)n; }
static void *kzalloc(size_t size, int flags) { (void)flags; return calloc(1,size); }
#define kfree free
static int pm_genpd_init(struct generic_pm_domain *d, void *g, bool off)
{ (void)d; (void)g; (void)off; return 0; }
static int of_genpd_add_provider_simple(struct device_node *n, struct generic_pm_domain *d)
{ (void)n; (void)d; return 0; }
static int pm_genpd_remove(struct generic_pm_domain *d) { (void)d; return 0; }
#include "clk-sdp1804-gpu.c"
int main(void)
{
 struct sdp1804_gpu_power gpu = { .base=mmio };
 struct device_node root = {0};
 u32 unrelated=BIT(3);
 child.enabled=false;
 assert(sdp1804_gpu_power_init(&root,mmio)==0);
 assert(reads==0 && writes==0); /* disabled means zero new MMIO */
 mmio[GPU_RESET/4]=unrelated;
 mmio[GPU_GATE/4]=unrelated;
 mmio[GPU_IDLE_REQ/4]=unrelated | GPU_IDLE;
 assert(sdp1804_gpu_on(&gpu.domain)==0);
 assert(writes==4);
 assert(offsets[0]==GPU_GATE && offsets[1]==GPU_RESET);
 assert(offsets[2]==GPU_RESET && offsets[3]==GPU_IDLE_REQ);
 assert(values[1]==(unrelated|GPU_BUS_NRESET));
 assert(values[2]==(unrelated|GPU_BUS_NRESET|GPU_CORE_NRESET));
 assert(values[3]==unrelated);
 writes=0;
	mmio[GPU_IDLE_ACK/4]=BIT(1); /* any nonzero vendor Ack word succeeds */
	assert(sdp1804_gpu_off(&gpu.domain)==0);
	assert(writes==4 && offsets[0]==GPU_IDLE_REQ && offsets[1]==GPU_RESET);
	assert(mmio[GPU_GATE/4]==unrelated && mmio[GPU_RESET/4]==unrelated);
 writes=0;
	mmio[GPU_GATE/4]|=GPU_GATE_ON;
	mmio[GPU_RESET/4]|=GPU_BUS_NRESET|GPU_CORE_NRESET;
	mmio[GPU_IDLE_REQ/4]=unrelated|GPU_IDLE;
	mmio[GPU_IDLE_ACK/4]=0;
 assert(sdp1804_gpu_off(&gpu.domain)==-ETIMEDOUT);
 assert(mmio[GPU_IDLE_REQ/4]==(unrelated|GPU_IDLE));
 writes=0;
	mmio[GPU_IDLE_ACK/4]=GPU_IDLE;
 assert(sdp1804_gpu_off(&gpu.domain)==0);
 assert(writes==4 && offsets[0]==GPU_IDLE_REQ && offsets[1]==GPU_RESET);
 assert(offsets[2]==GPU_RESET && offsets[3]==GPU_GATE);
 assert(mmio[GPU_GATE/4]==unrelated && mmio[GPU_RESET/4]==unrelated);
 writes=0;
 child.enabled=true;
 mmio[GPU_GATE/4]|=GPU_GATE_ON; /* mixed reset/gate boot state */
 assert(sdp1804_gpu_power_init(&root,mmio)==-EINVAL);
 assert(writes==0);
 return 0;
}
