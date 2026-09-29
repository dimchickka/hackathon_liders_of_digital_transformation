
void FUN_100001f6(void)

{
  bool bVar1;
  undefined4 *puVar2;
  undefined4 uVar3;
  int iVar4;
  undefined4 *puVar5;
  int *piVar6;
  int *piVar7;
  
  puVar2 = DAT_10000264;
  if (*DAT_1000026c == 0) {
    piVar6 = &DAT_10000238;
    uVar3 = 0;
    while( true ) {
      puVar2 = DAT_10000274;
      iVar4 = *piVar6;
      piVar7 = piVar6 + 1;
      piVar6 = piVar6 + 3;
      puVar5 = DAT_10000270;
      if (iVar4 == 0) break;
      uVar3 = FUN_10000232(uVar3,iVar4,*piVar7);
    }
    for (; puVar5 != puVar2; puVar5 = puVar5 + 1) {
      *puVar5 = 0;
    }
    (*DAT_10000278)();
    (*DAT_1000027c)();
    (*DAT_10000280)();
    do {
      software_bkpt(0);
    } while( true );
  }
  *DAT_10000268 = (int)DAT_10000264;
  bVar1 = (bool)isCurrentModePrivileged();
  if (bVar1) {
    setMainStackPointer(*puVar2);
  }
                    /* WARNING: Could not recover jumptable at 0x100001f4. Too many branches */
                    /* WARNING: Treating indirect jump as call */
  (*(code *)puVar2[1])(puVar2 + 2,*puVar2);
  return;
}

