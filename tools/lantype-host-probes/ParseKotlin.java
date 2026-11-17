import java.nio.file.*;
import java.util.*;
import org.jetbrains.kotlin.cli.jvm.compiler.*;
import org.jetbrains.kotlin.config.CompilerConfiguration;
import org.jetbrains.kotlin.com.intellij.openapi.util.Disposer;
import org.jetbrains.kotlin.com.intellij.psi.PsiErrorElement;
import org.jetbrains.kotlin.com.intellij.psi.util.PsiTreeUtil;
import org.jetbrains.kotlin.psi.KtPsiFactory;
public class ParseKotlin {
 public static void main(String[] args) throws Exception {
  var disposable=Disposer.newDisposable();
  int errors=0;
  try {
   var env=KotlinCoreEnvironment.createForProduction(disposable,new CompilerConfiguration(),EnvironmentConfigFiles.JVM_CONFIG_FILES);
   var factory=new KtPsiFactory(env.getProject(),false);
   for(String path:args) {
    var file=factory.createFile(Path.of(path).getFileName().toString(),Files.readString(Path.of(path)));
    var found=PsiTreeUtil.collectElementsOfType(file,PsiErrorElement.class);
    for(var err:found) { System.out.println("ERROR "+path+":"+err.getTextRange()+" "+err.getErrorDescription()); errors++; }
    if(found.isEmpty()) System.out.println("PASS syntax "+path);
   }
  } finally { Disposer.dispose(disposable); }
  System.out.println("Kotlin syntax errors: "+errors);
  if(errors!=0) System.exit(1);
 }
}
