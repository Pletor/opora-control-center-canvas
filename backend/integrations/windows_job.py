"""Windows Job Object (KILL_ON_JOB_CLOSE) pro ohraničené lokální subprocesy.

Proces se spouští pozastavený, přiřadí se do jobu a teprve pak se obnoví, takže
celý strom potomků skončí spolu s jobem (zavření handle nebo terminate_wait).
"""

import ctypes
import os
import time


class WindowsJob:
    """KILL_ON_JOB_CLOSE job. A process starts suspended until assigned."""

    CREATE_SUSPENDED = 0x00000004
    CREATE_NO_WINDOW = 0x08000000
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
    JobObjectExtendedLimitInformation = 9
    JobObjectBasicAccountingInformation = 1

    def __init__(self):
        if os.name != "nt":
            raise OSError("Windows Job Object není dostupný.")
        from ctypes import wintypes

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [
                (name, ctypes.c_ulonglong)
                for name in (
                    "ReadOperationCount",
                    "WriteOperationCount",
                    "OtherOperationCount",
                    "ReadTransferCount",
                    "WriteTransferCount",
                    "OtherTransferCount",
                )
            ]

        class BASIC_LIMIT(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_longlong),
                ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class EXTENDED(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", BASIC_LIMIT),
                ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        class ACCOUNTING(ctypes.Structure):
            _fields_ = [
                ("TotalUserTime", ctypes.c_longlong),
                ("TotalKernelTime", ctypes.c_longlong),
                ("ThisPeriodTotalUserTime", ctypes.c_longlong),
                ("ThisPeriodTotalKernelTime", ctypes.c_longlong),
                ("TotalPageFaultCount", wintypes.DWORD),
                ("TotalProcesses", wintypes.DWORD),
                ("ActiveProcesses", wintypes.DWORD),
                ("TotalTerminatedProcesses", wintypes.DWORD),
            ]

        self._accounting = ACCOUNTING
        self.k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.ntdll = ctypes.WinDLL("ntdll", use_last_error=True)
        self.k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        self.k32.CreateJobObjectW.restype = wintypes.HANDLE
        self.k32.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        self.k32.SetInformationJobObject.restype = wintypes.BOOL
        self.k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self.k32.AssignProcessToJobObject.restype = wintypes.BOOL
        self.k32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self.k32.TerminateJobObject.restype = wintypes.BOOL
        self.k32.QueryInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.c_void_p,
        ]
        self.k32.QueryInformationJobObject.restype = wintypes.BOOL
        self.k32.CloseHandle.argtypes = [wintypes.HANDLE]
        self.k32.CloseHandle.restype = wintypes.BOOL
        self.ntdll.NtResumeProcess.argtypes = [wintypes.HANDLE]
        self.ntdll.NtResumeProcess.restype = ctypes.c_long
        self.handle = self.k32.CreateJobObjectW(None, None)
        if not self.handle:
            raise OSError("Nelze vytvořit bezpečnostní Job Object.")
        info = EXTENDED()
        info.BasicLimitInformation.LimitFlags = self.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.k32.SetInformationJobObject(
            self.handle,
            self.JobObjectExtendedLimitInformation,
            ctypes.byref(info),
            ctypes.sizeof(info),
        ):
            self.close()
            raise OSError("Nelze nastavit bezpečnostní Job Object.")

    def assign_and_resume(self, popen):
        handle = ctypes.c_void_p(popen._handle)
        if not self.k32.AssignProcessToJobObject(self.handle, handle):
            raise OSError("Nelze přiřadit proces do bezpečnostního Job Object.")
        if self.ntdll.NtResumeProcess(handle) != 0:
            raise OSError("Nelze bezpečně spustit ohraničený proces.")

    def active_processes(self):
        info = self._accounting()
        ok = self.k32.QueryInformationJobObject(
            self.handle,
            self.JobObjectBasicAccountingInformation,
            ctypes.byref(info),
            ctypes.sizeof(info),
            None,
        )
        return int(info.ActiveProcesses) if ok else None

    def terminate_wait(self, timeout=5):
        if not self.k32.TerminateJobObject(self.handle, 1):
            return False
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if self.active_processes() == 0:
                return True
            time.sleep(0.02)
        return self.active_processes() == 0

    def close(self):
        if getattr(self, "handle", None):
            self.k32.CloseHandle(self.handle)
            self.handle = None
