
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void FUN_100009a4(void)

{
  uint uVar1;
  char *pcVar2;
  uint *puVar3;
  uint uVar4;
  longlong lVar5;
  undefined8 uVar6;
  
  pcVar2 = DAT_10000a98;
  if (*DAT_10000a94 == '\0') {
    *DAT_10000a98 = '\0';
  }
  else if (*DAT_10000a98 == '\0') {
    _DAT_d0000018 = 0x100;
    *DAT_10000a9c = 0;
    lVar5 = FUN_100025c8();
    lVar5 = lVar5 + (ulonglong)DAT_10000aa0;
    if (lVar5 < 0) {
      lVar5 = CONCAT44(DAT_10000aa8,0xffffffff);
    }
    *(longlong *)DAT_10000aa4 = lVar5;
    *pcVar2 = '\x01';
  }
  else {
    uVar6 = FUN_100025c8();
    puVar3 = DAT_10000aa4;
    uVar4 = DAT_10000aa4[1] - (int)((ulonglong)uVar6 >> 0x20);
    uVar1 = (uint)(*DAT_10000aa4 < (uint)uVar6);
    if (((int)(uVar4 - uVar1) < 1) && ((uVar4 != uVar1 || (*DAT_10000aa4 == (uint)uVar6)))) {
      lVar5 = FUN_100025c8();
      lVar5 = lVar5 + (ulonglong)DAT_10000aa0;
      if (lVar5 < 0) {
        lVar5 = CONCAT44(DAT_10000aa8,0xffffffff);
      }
      *(longlong *)puVar3 = lVar5;
      _DAT_d0000018 = 0x100;
      uVar4 = *DAT_10000a9c + 1;
      _DAT_d0000014 = 1 << *(sbyte *)(DAT_10000aac + *DAT_10000a9c);
      if (uVar4 < 10) {
        *DAT_10000a9c = uVar4;
      }
      else {
        *DAT_10000a9c = 0;
      }
    }
  }
  return;
}

