# Send only to the foreground window owned by the isolated test browser.
import ctypes as c, ctypes.wintypes as w, json, sys,time
u=c.windll.user32
im=c.windll.imm32
u.GetForegroundWindow.restype=w.HWND
u.GetKeyboardLayout.restype=w.HKL
im.ImmGetContext.restype=w.HANDLE
im.ImmGetContext.argtypes=[w.HWND]
im.ImmGetCandidateListW.argtypes=[w.HANDLE,w.DWORD,w.LPVOID,w.DWORD]
im.ImmReleaseContext.argtypes=[w.HWND,w.HANDLE]
class Gui(c.Structure):
 _fields_=[('cbSize',w.DWORD),('flags',w.DWORD)]+[(name,w.HWND) for name in ('active','focus','capture','menu','move','caret')]+[('rect',w.RECT)]
pid=int(sys.argv[1]); result={'browser_pid':pid,'action':sys.argv[2],'sent':[]}
def check():
 hwnd=u.GetForegroundWindow(); owner=w.DWORD()
 tid=u.GetWindowThreadProcessId(w.HWND(hwnd),c.byref(owner))
 if owner.value!=pid:raise ValueError('isolated browser is not foreground')
 info=Gui();info.cbSize=c.sizeof(info);u.GetGUIThreadInfo(tid,c.byref(info))
 return tid,info.focus or hwnd
try:
 tid,hwnd=check()
 lang=u.GetKeyboardLayout(tid)&0xffff
 result['language_id']=hex(lang)
 if (lang&0x3ff)!=4:raise ValueError('foreground input language is not Chinese')
 if sys.argv[2]=='type':keys=[ord(x) for x in 'NIHAO']
 elif sys.argv[2]=='confirm':keys=[0x20]
 else:raise ValueError('unknown action')
 for vk in keys:
  check();u.keybd_event(vk,0,0,0);u.keybd_event(vk,0,2,0);result['sent'].append(vk);time.sleep(0.12)
 time.sleep(.45)
 context=im.ImmGetContext(hwnd)
 if context:
  result['candidate_bytes']=im.ImmGetCandidateListW(context,0,None,0)
  im.ImmReleaseContext(hwnd,context)
except ValueError as e:result['reason']=str(e)
print(json.dumps(result))
